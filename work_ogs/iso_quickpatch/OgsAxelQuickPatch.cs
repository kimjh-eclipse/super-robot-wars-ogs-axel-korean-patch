using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;

// 슈퍼로봇대전 OGs (PS2) 액셀 역할 교체 패치 — 제자리 ISO 빠른패처
//
// D2DHD_kr/iso_quickpatch 패처와 같은 구조. 기준 ISO(한국어화 v1.4.3s1)와
// 패치본 ISO 크기가 완전히 동일하므로(4,518,150,144B) ISO 내부 파일을 찾을
// 필요 없이 **절대 오프셋 구간**만 덮어쓰면 된다.
//
// 패치 데이터 OGS_ISO_ranges.bin 포맷 (build_range_pack.py 생성).
// D2 와 같은 이유로 exe 에 임베드하지 않고 같은 폴더의 별도 파일로 배포한다
// (미서명 exe + 대용량 블롭은 Defender 오탐을 유발):
//   magic "OGSAXLRNG" / u32 version / u16 titleLen + utf8 title
//   u64 isoSize / 32B srcHash / 32B dstHash / u32 rangeCount
//   rangeCount x { u64 offset, u32 length, length bytes }
internal static class OgsAxelQuickPatch
{
    private const string VersionText = "v20261028";
    private const string PatchResourceName = "OGS_ISO_ranges.bin";
    private const string HiddenResourceName = "OGS_hidden_rewards.bin";
    private const string OukaResourceName = "OGS_ouka_zengar.bin";
    private const string OukaHiddenResourceName = "OGS_ouka_zengar_hidden.bin";
    // 선택적 사이드카: 직전 릴리즈 적용본을 핫픽스본으로 올리는 소구간 팩.
    // 없으면 기준본→최신본 팩만으로 동작한다.
    private const string UpgradeResourceName = "OGS_ISO_ranges_upgrade.bin";
    private const string PackMagic = "OGSAXLRNG";
    private const string BackupMagic = "OGSAXLBAK";
    private const string BackupExt = ".ogsbak";
    private const int FormatVersion = 1;
    private const int HashSize = 32;
    private const uint AttachParentProcess = 0xFFFFFFFF;

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AttachConsole(uint processId);

    private sealed class PatchRange
    {
        public long Offset;
        public byte[] Data;
    }

    private sealed class Pack
    {
        public string Title;
        public long IsoSize;
        public byte[] SourceHash;
        public byte[] TargetHash;
        public List<PatchRange> Ranges;
        public long PayloadBytes;
    }

    private enum Mode { Patch, Verify }

    // ---------- 리소스 ----------

    private static Stream OpenPatchData(string name, bool required)
    {
        string exeDir = Path.GetDirectoryName(
            Assembly.GetExecutingAssembly().Location);
        string[] candidates = new string[]
        {
            string.IsNullOrEmpty(exeDir) ? name : Path.Combine(exeDir, name),
            Path.Combine(Directory.GetCurrentDirectory(), name),
        };
        foreach (string path in candidates)
        {
            if (File.Exists(path))
                return new FileStream(path, FileMode.Open, FileAccess.Read,
                                      FileShare.Read, 1 << 20);
        }
        if (!required) return null;
        throw new FileNotFoundException(
            "패치 데이터 파일을 찾을 수 없습니다: " + name + "\n\n" +
            "이 프로그램은 같은 폴더에 있는 " + name + " 을 읽습니다.\n" +
            "ZIP 을 풀 때 patcher 폴더의 파일들을 함께 두세요.\n" +
            "exe 만 따로 옮기면 동작하지 않습니다.");
    }

    // 기본 팩(기준본→최신본)은 필수, 업그레이드 팩(직전 릴리즈→최신본)은 선택.
    // 두 팩의 TargetHash 는 같아야 하며 LoadPacks 가 이를 검증한다.
    private static List<Pack> LoadPacks()
    {
        List<Pack> packs = new List<Pack>();
        packs.Add(LoadPack(OpenPatchData(PatchResourceName, true)));
        // 업그레이드 팩은 OGS_ISO_ranges_upgrade*.bin 전부 (직전 릴리즈들 → 최신본)
        string exeDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        List<string> dirs = new List<string>();
        if (!string.IsNullOrEmpty(exeDir)) dirs.Add(exeDir);
        dirs.Add(Directory.GetCurrentDirectory());
        HashSet<string> seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (string dir in dirs)
        {
            if (!Directory.Exists(dir)) continue;
            foreach (string path in Directory.GetFiles(dir, "OGS_ISO_ranges_upgrade*.bin"))
            {
                if (!seen.Add(Path.GetFileName(path))) continue;
                Pack up = LoadPack(new FileStream(path, FileMode.Open, FileAccess.Read,
                                                  FileShare.Read, 1 << 20));
                if (!string.Equals(Hex(up.TargetHash), Hex(packs[0].TargetHash),
                                   StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException(
                        "업그레이드 팩의 결과 해시가 기본 팩과 다릅니다: " + Path.GetFileName(path));
                packs.Add(up);
            }
        }
        return packs;
    }

    private static Pack LoadPack(Stream resource)
    {

        using (resource)
        using (BinaryReader r = new BinaryReader(resource, Encoding.UTF8))
        {
            byte[] magic = r.ReadBytes(PackMagic.Length);
            if (Encoding.ASCII.GetString(magic) != PackMagic)
                throw new InvalidDataException("패치 리소스 형식이 올바르지 않습니다.");
            int version = r.ReadInt32();
            if (version != FormatVersion)
                throw new InvalidDataException("지원하지 않는 패치 버전: " + version);

            int titleLen = r.ReadUInt16();
            string title = Encoding.UTF8.GetString(r.ReadBytes(titleLen));

            Pack pack = new Pack();
            pack.Title = title;
            pack.IsoSize = r.ReadInt64();
            pack.SourceHash = r.ReadBytes(HashSize);
            pack.TargetHash = r.ReadBytes(HashSize);

            int count = r.ReadInt32();
            if (count < 0 || count > 1000000) throw new InvalidDataException("잘못된 구간 수");
            pack.Ranges = new List<PatchRange>(count);
            long payload = 0;
            for (int i = 0; i < count; i++)
            {
                PatchRange range = new PatchRange();
                range.Offset = r.ReadInt64();
                int length = r.ReadInt32();
                if (range.Offset < 0 || length <= 0 || range.Offset > pack.IsoSize - length)
                    throw new InvalidDataException("ISO 범위를 벗어난 패치 구간");
                range.Data = r.ReadBytes(length);
                if (range.Data.Length != length)
                    throw new InvalidDataException("패치 리소스가 손상되었습니다.");
                payload += length;
                pack.Ranges.Add(range);
            }
            pack.PayloadBytes = payload;
            if (resource.Position != resource.Length)
                throw new InvalidDataException("패치 리소스 뒤에 잉여 데이터가 있습니다.");
            return pack;
        }
    }

    private static Pack[] LoadOption(Pack full, string resourceName, string title)
    {
        using (Stream stream = OpenPatchData(resourceName, true))
        using (BinaryReader r = new BinaryReader(stream, Encoding.UTF8))
        {
            if (Encoding.ASCII.GetString(r.ReadBytes(8)) != "OGSHID01")
                throw new InvalidDataException(title + " 데이터 형식 오류");
            long size = r.ReadInt64();
            byte[] source = r.ReadBytes(32), target = r.ReadBytes(32);
            if (size != full.IsoSize || Hex(source) != Hex(full.TargetHash))
                throw new InvalidDataException(title + " 데이터와 기본 패치 버전이 다릅니다.");
            Pack on = new Pack { Title = title + " 켜기", IsoSize = size,
                SourceHash = source, TargetHash = target, Ranges = new List<PatchRange>() };
            Pack off = new Pack { Title = title + " 끄기", IsoSize = size,
                SourceHash = target, TargetHash = source, Ranges = new List<PatchRange>() };
            int count = r.ReadInt32();
            if (count < 1 || count > 1000000) throw new InvalidDataException("잘못된 옵션 구간 수");
            long end = 0;
            for (int i = 0; i < count; i++)
            {
                long offset = r.ReadInt64(); int length = r.ReadInt32();
                if (offset < end || length < 1 || offset > size - length)
                    throw new InvalidDataException("잘못된 옵션 구간");
                byte[] before = r.ReadBytes(length), after = r.ReadBytes(length);
                if (before.Length != length || after.Length != length) throw new EndOfStreamException();
                off.Ranges.Add(new PatchRange { Offset = offset, Data = before });
                on.Ranges.Add(new PatchRange { Offset = offset, Data = after });
                off.PayloadBytes += length; on.PayloadBytes += length; end = offset + length;
            }
            if (stream.Position != stream.Length) throw new InvalidDataException("옵션 데이터 길이 오류");
            return new Pack[] { on, off };
        }
    }

    private sealed class Feature
    {
        public int Bit;
        public List<PatchRange> On = new List<PatchRange>();
        public List<PatchRange> Off = new List<PatchRange>();
    }
    private sealed class FeatureOptions
    {
        public byte[][] Hashes = new byte[32][];
        public List<Feature> Features = new List<Feature>();
        public List<Pack> Aliases = new List<Pack>();
    }
    private static List<PatchRange>[] ReadFeatureRanges(BinaryReader r, long size)
    {
        int count = r.ReadInt32();
        if (count < 1 || count > 1000000) throw new InvalidDataException("잘못된 추가 옵션 구간 수");
        List<PatchRange> off = new List<PatchRange>(), on = new List<PatchRange>();
        long end = 0;
        for (int i = 0; i < count; i++)
        {
            long at = r.ReadInt64(); int len = r.ReadInt32();
            if (at < end || len < 1 || at > size - len) throw new InvalidDataException("추가 옵션 범위 오류");
            byte[] a = r.ReadBytes(len), b = r.ReadBytes(len);
            if (a.Length != len || b.Length != len) throw new EndOfStreamException();
            off.Add(new PatchRange { Offset = at, Data = a });
            on.Add(new PatchRange { Offset = at, Data = b }); end = at + len;
        }
        return new List<PatchRange>[] { off, on };
    }
    private static FeatureOptions LoadFeatures(Pack full)
    {
        using (Stream stream = OpenPatchData("OGS_optional_features.bin", true))
        using (BinaryReader r = new BinaryReader(stream, Encoding.UTF8))
        {
            if (Encoding.ASCII.GetString(r.ReadBytes(8)) != "OGSOPT02" || r.ReadInt64() != full.IsoSize ||
                Hex(r.ReadBytes(32)) != Hex(full.TargetHash)) throw new InvalidDataException("추가 옵션 버전 불일치");
            FeatureOptions options = new FeatureOptions();
            if (r.ReadInt32() != 32) throw new InvalidDataException("옵션 조합 수 오류");
            HashSet<string> hashes = new HashSet<string>();
            for (int i = 0; i < 32; i++)
            {
                int mask = r.ReadInt32(); byte[] hash = r.ReadBytes(32);
                if (mask != i || hash.Length != 32 || !hashes.Add(Hex(hash))) throw new InvalidDataException("옵션 조합 해시 오류");
                options.Hashes[mask] = hash;
            }
            if (Hex(options.Hashes[0]) != Hex(full.TargetHash) || r.ReadInt32() != 3)
                throw new InvalidDataException("추가 옵션 기준 오류");
            foreach (int expected in new int[] { 4, 8, 16 })
            {
                int bit = r.ReadInt32();
                if (bit != expected) throw new InvalidDataException("추가 옵션 번호 오류");
                List<PatchRange>[] ranges = ReadFeatureRanges(r, full.IsoSize);
                options.Features.Add(new Feature { Bit = bit, Off = ranges[0], On = ranges[1] });
            }
            int aliases = r.ReadInt32();
            if (aliases < 0 || aliases > 32) throw new InvalidDataException("중간 적용본 수 오류");
            for (int i = 0; i < aliases; i++)
            {
                byte[] source = r.ReadBytes(32); int target = r.ReadInt32();
                if (source.Length != 32 || target < 0 || target > 3) throw new InvalidDataException("중간 적용본 정보 오류");
                List<PatchRange>[] ranges = ReadFeatureRanges(r, full.IsoSize);
                Pack alias = new Pack { Title = "중간 적용본 정규화", IsoSize = full.IsoSize,
                    SourceHash = source, TargetHash = options.Hashes[target], Ranges = ranges[0] };
                foreach (PatchRange range in alias.Ranges) alias.PayloadBytes += range.Data.Length;
                options.Aliases.Add(alias);
            }
            if (stream.Position != stream.Length) throw new InvalidDataException("추가 옵션 데이터 길이 오류");
            return options;
        }
    }
    private static Pack FeaturePack(Pack full, FeatureOptions options, int mask, byte[] source, byte[] target, bool on)
    {
        Pack pack = new Pack { Title = on ? "추가 옵션 켜기" : "추가 옵션 끄기", IsoSize = full.IsoSize,
            SourceHash = source, TargetHash = target, Ranges = new List<PatchRange>() };
        foreach (Feature feature in options.Features)
            if ((mask & feature.Bit) != 0)
                foreach (PatchRange range in on ? feature.On : feature.Off)
                { pack.Ranges.Add(range); pack.PayloadBytes += range.Data.Length; }
        return pack;
    }

    private sealed class CommonFix
    {
        public byte[][] Hashes = new byte[32][], PriorHashes = new byte[32][];
        public List<PatchRange>[] On = new List<PatchRange>[32], Off = new List<PatchRange>[32];
        public List<PatchRange> PriorOn, PriorOff;
    }
    private static CommonFix LoadCommonFix(Pack full, FeatureOptions features)
    {
        using (Stream stream = OpenPatchData("OGS_common_fix.bin", true))
        using (BinaryReader r = new BinaryReader(stream, Encoding.UTF8))
        {
            if (Encoding.ASCII.GetString(r.ReadBytes(8)) != "OGSFIX02" || r.ReadInt64() != full.IsoSize || r.ReadInt32() != 32)
                throw new InvalidDataException("공통 수정 데이터 형식 오류");
            CommonFix fix = new CommonFix(); HashSet<string> hashes = new HashSet<string>();
            for (int i = 0; i < 32; i++)
            {
                int mask = r.ReadInt32(); byte[] old = r.ReadBytes(32), target = r.ReadBytes(32);
                if (mask != i || Hex(old) != Hex(features.Hashes[i]) || target.Length != 32 || !hashes.Add(Hex(target)))
                    throw new InvalidDataException("공통 수정 버전 불일치");
                fix.Hashes[i] = target;
                List<PatchRange>[] ranges = ReadFeatureRanges(r, full.IsoSize); fix.Off[i] = ranges[0]; fix.On[i] = ranges[1];
            }
            for (int i = 0; i < 32; i++)
            {
                fix.PriorHashes[i] = r.ReadBytes(32);
                if (fix.PriorHashes[i].Length != 32) throw new EndOfStreamException();
            }
            List<PatchRange>[] prior = ReadFeatureRanges(r, full.IsoSize);fix.PriorOff = prior[0];fix.PriorOn = prior[1];
            if (stream.Position != stream.Length) throw new InvalidDataException("공통 수정 길이 오류");
            return fix;
        }
    }
    private static Pack FixPack(Pack full, CommonFix fix, byte[] source, byte[] target, bool on)
    {
        int mask = -1;
        for (int i = 0; i < 32; i++) if (Hex(on ? target : source) == Hex(fix.Hashes[i])) { mask = i; break; }
        if (mask < 0) throw new InvalidDataException("공통 수정 조합 해시 오류");
        Pack pack = new Pack { Title = on ? "워단 생존·삼식 지급·무명 보충" : "공통 수정 전환", IsoSize = full.IsoSize,
            SourceHash = source, TargetHash = target, Ranges = on ? fix.On[mask] : fix.Off[mask] };
        foreach (PatchRange range in pack.Ranges) pack.PayloadBytes += range.Data.Length;
        return pack;
    }
    private static Pack SelectFixedPlan(List<Pack> packs, Pack[] option, Pack[] oukaBase, Pack[] oukaHidden,
        FeatureOptions features, CommonFix fix, string current, int selected)
    {
        Pack prefix = null;
        for (int i = 0; i < 32; i++)
            if (current == Hex(fix.Hashes[i]))
            { prefix = FixPack(packs[0], fix, fix.Hashes[i], features.Hashes[i], false); current = Hex(features.Hashes[i]); break; }
        if (prefix == null)
            for (int i = 0; i < 32; i++)
                if (current == Hex(fix.PriorHashes[i]))
                {
                    prefix = new Pack { Title = "v20261027.1 업데이트", IsoSize = packs[0].IsoSize,
                        SourceHash = fix.PriorHashes[i], TargetHash = features.Hashes[i], Ranges = fix.PriorOff };
                    foreach (PatchRange range in prefix.Ranges) prefix.PayloadBytes += range.Data.Length;
                    current = Hex(features.Hashes[i]); break;
                }
        Pack plan = SelectPlan(packs, option, oukaBase, oukaHidden, features, current, selected);
        if (plan == null) return null;
        if (prefix != null) plan = Combine(prefix, plan);
        return Combine(plan, FixPack(packs[0], fix, features.Hashes[selected], fix.Hashes[selected], true));
    }

    private static Pack Combine(Pack first, Pack second)
    {
        if (Hex(first.TargetHash) != Hex(second.SourceHash)) throw new InvalidDataException("패치 연결 오류");
        Pack result = new Pack { Title = first.Title + " + " + second.Title,
            IsoSize = first.IsoSize, SourceHash = first.SourceHash, TargetHash = second.TargetHash,
            PayloadBytes = first.PayloadBytes + second.PayloadBytes, Ranges = new List<PatchRange>(first.Ranges) };
        // Order is intentional: optional script bytes override base-patch ranges.
        result.Ranges.AddRange(second.Ranges);
        return result;
    }

    // ---------- 해시 ----------

    private static string Sha256(string path, Action<long, long> progress)
    {
        long total = new FileInfo(path).Length;
        long done = 0;
        using (SHA256 sha = SHA256.Create())
        using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read,
                                              FileShare.Read, 1 << 20))
        {
            byte[] buffer = new byte[4 << 20];
            int read;
            while ((read = fs.Read(buffer, 0, buffer.Length)) > 0)
            {
                sha.TransformBlock(buffer, 0, read, null, 0);
                done += read;
                if (progress != null) progress(done, total);
            }
            sha.TransformFinalBlock(new byte[0], 0, 0);
            return BitConverter.ToString(sha.Hash).Replace("-", string.Empty);
        }
    }

    private static string Hex(byte[] data)
    {
        return BitConverter.ToString(data).Replace("-", string.Empty);
    }

    // ---------- 동작 ----------

    private static Pack SelectPlan(List<Pack> packs, Pack[] option, Pack[] oukaBase, Pack[] oukaHidden,
        FeatureOptions features, string current, int selected)
    {
        Pack full = packs[0];
        bool hidden = (selected & 1) != 0, ouka = (selected & 2) != 0;
        Pack prefix = null;
        string normalized = current;
        for (int mask = 4; mask < 32; mask++)
            if (current == Hex(features.Hashes[mask]))
            {
                prefix = FeaturePack(full, features, mask, features.Hashes[mask], features.Hashes[mask & 3], false);
                normalized = Hex(prefix.TargetHash); break;
            }
        if (prefix == null)
            foreach (Pack alias in features.Aliases)
                if (current == Hex(alias.SourceHash)) { prefix = alias; normalized = Hex(alias.TargetHash); break; }
        Pack pack = null;
        foreach (Pack p in packs)
            if (normalized == Hex(p.SourceHash)) { pack = p; break; }
        if (normalized == Hex(oukaHidden[0].TargetHash)) pack = Combine(oukaHidden[1], option[1]);
        else if (normalized == Hex(oukaBase[0].TargetHash)) pack = oukaBase[1];
        else if (normalized == Hex(option[0].TargetHash)) pack = option[1];
        else if (normalized == Hex(full.TargetHash))
            pack = new Pack { Title = "기본 패치", IsoSize = full.IsoSize,
                SourceHash = full.TargetHash, TargetHash = full.TargetHash, Ranges = new List<PatchRange>() };
        if (pack != null)
        {
            if (prefix != null) pack = Combine(prefix, pack);
            if (hidden) pack = Combine(pack, option[0]);
            if (ouka) pack = Combine(pack, hidden ? oukaHidden[0] : oukaBase[0]);
            if ((selected & 28) != 0)
                pack = Combine(pack, FeaturePack(full, features, selected, pack.TargetHash, features.Hashes[selected], true));
        }
        return pack;
    }

    private static void CheckOptionTransitions()
    {
        List<Pack> packs = LoadPacks(); Pack full = packs[0];
        Pack[] hidden = LoadOption(full, HiddenResourceName, "숨겨진 요소");
        Pack[] bundle = LoadOption(full, OukaResourceName, "오우카·젠가");
        Pack[] both = LoadOption(hidden[0], OukaHiddenResourceName, "오우카·젠가");
        FeatureOptions features = LoadFeatures(full);
        if (Hex(features.Hashes[1]) != Hex(hidden[0].TargetHash) ||
            Hex(features.Hashes[2]) != Hex(bundle[0].TargetHash) ||
            Hex(features.Hashes[3]) != Hex(both[0].TargetHash)) throw new InvalidDataException("기존 옵션 해시 불일치");
        CommonFix fix = LoadCommonFix(full, features);
        SortedDictionary<long, byte> defaults = new SortedDictionary<long, byte>();
        List<PatchRange> off = new List<PatchRange>(hidden[1].Ranges); off.AddRange(bundle[1].Ranges);
        foreach (Feature feature in features.Features) off.AddRange(feature.Off);

        foreach (PatchRange range in off)
            for (int i = 0; i < range.Data.Length; i++)
            {
                byte previous;
                if (defaults.TryGetValue(range.Offset + i, out previous) && previous != range.Data[i])
                    throw new InvalidDataException("기본 옵션 바이트 충돌");
                defaults[range.Offset + i] = range.Data[i];
            }
        for (int mask = 0; mask < 32; mask++)
            foreach (PatchRange range in fix.Off[mask])
                for (int i = 0; i < range.Data.Length; i++)
                    if (!defaults.ContainsKey(range.Offset + i)) defaults[range.Offset + i] = range.Data[i];
        Dictionary<long, int> index = new Dictionary<long, int>();
        byte[] initial = new byte[defaults.Count]; int pos = 0;
        foreach (KeyValuePair<long, byte> item in defaults) { index[item.Key] = pos; initial[pos++] = item.Value; }
        byte[][] states = new byte[32][];
        for (int mask = 0; mask < 32; mask++)
        {
            states[mask] = (byte[])initial.Clone();
            if ((mask & 1) != 0) ApplyState(hidden[0], index, states[mask]);
            if ((mask & 2) != 0) ApplyState((mask & 1) != 0 ? both[0] : bundle[0], index, states[mask]);
            ApplyState(FeaturePack(full, features, mask, full.TargetHash, features.Hashes[mask], true), index, states[mask]);
        }
        byte[][] fixedStates = new byte[32][];
        for (int mask = 0; mask < 32; mask++)
        {
            fixedStates[mask] = (byte[])states[mask].Clone();
            ApplyState(FixPack(full, fix, features.Hashes[mask], fix.Hashes[mask], true), index, fixedStates[mask]);
        }
        byte[][] priorStates = new byte[32][];
        for (int mask = 0; mask < 32; mask++)
        {
            priorStates[mask] = (byte[])states[mask].Clone();
            Pack priorOn = new Pack { Ranges = fix.PriorOn }; ApplyState(priorOn, index, priorStates[mask]);
        }
        int cases = 0;
        for (int generation = 0; generation < 3; generation++)
            for (int source = 0; source < 32; source++)
                for (int target = 0; target < 32; target++)
                {
                    byte[] sourceHash = generation == 0 ? features.Hashes[source] : (generation == 1 ? fix.PriorHashes[source] : fix.Hashes[source]);
                    Pack plan = SelectFixedPlan(packs, hidden, bundle, both, features, fix, Hex(sourceHash), target);
                    if (plan == null || Hex(plan.SourceHash) != Hex(sourceHash) || Hex(plan.TargetHash) != Hex(fix.Hashes[target]))
                        throw new InvalidDataException("옵션 연결 해시 오류");
                    byte[] state = (byte[])(generation == 0 ? states[source] : (generation == 1 ? priorStates[source] : fixedStates[source])).Clone(); ApplyState(plan, index, state);
                    for (int i = 0; i < state.Length; i++)
                        if (state[i] != fixedStates[target][i]) throw new InvalidDataException("옵션 전환 바이트 오류: " + source + " -> " + target);
                    cases++;
                }
        Console.WriteLine("PASS: " + cases + " option transitions; Wodan/Type3/Mumei common story fixes preserved.");
    }
    private static void ApplyState(Pack pack, Dictionary<long, int> index, byte[] state)
    {
        foreach (PatchRange range in pack.Ranges)
            for (int i = 0; i < range.Data.Length; i++)
            {
                int at;
                if (!index.TryGetValue(range.Offset + i, out at)) throw new InvalidDataException("옵션 이외 바이트 쓰기");
                state[at] = range.Data[i];
            }
    }

    private static void Run(string isoPath, Mode mode, bool hidden, bool ouka, bool rewards, bool enemy, bool spirits, Action<string> log,
                            Action<int> progress)
    {
        List<Pack> packs = LoadPacks();
        Pack full = packs[0];
        Pack[] option = LoadOption(full, HiddenResourceName, "숨겨진 요소 자동 습득");
        Pack[] oukaBase = LoadOption(full, OukaResourceName, "오우카 생존·젠가 밸런스");
        Pack[] oukaHidden = LoadOption(option[0], OukaHiddenResourceName, "오우카 생존·젠가 밸런스");
        FeatureOptions features = LoadFeatures(full);
        int selected = (hidden ? 1 : 0) | (ouka ? 2 : 0) | (rewards ? 4 : 0) | (enemy ? 8 : 0) | (spirits ? 16 : 0);
        CommonFix fix = LoadCommonFix(full, features);
        string desiredHash = Hex(fix.Hashes[selected]);
        log("워단 생존·37화 삼식 지급·무명 보충: 기본 적용");
        log("자금 +20% · PP 2배: " + (rewards ? "선택" : "선택 안 함"));
        log("적 강화: " + (enemy ? "선택" : "선택 안 함"));
        log("액셀·제오라 정신기 변경: " + (spirits ? "선택" : "선택 안 함"));
        log("오우카 생존 + 젠가 밸런스: " + (ouka ? "선택" : "선택 안 함"));
        log("숨겨진 요소 자동 습득: " + (hidden ? "선택" : "선택 안 함"));
        log(full.Title);
        log("패처 " + VersionText);
        log(string.Format(CultureInfo.InvariantCulture,
            "구간 {0:N0}개 / 페이로드 {1:N0}B", full.Ranges.Count, full.PayloadBytes));
        if (packs.Count > 1)
            log(string.Format(CultureInfo.InvariantCulture, "업그레이드 팩 {0}개 감지: 이전 릴리즈 적용본도 처리할 수 있습니다.", packs.Count - 1));
        log(string.Empty);

        if (!File.Exists(isoPath))
            throw new FileNotFoundException("ISO 를 찾을 수 없습니다: " + isoPath);

        FileInfo info = new FileInfo(isoPath);
        if (info.IsReadOnly)
            throw new IOException("ISO 가 읽기 전용입니다. 속성에서 읽기 전용을 해제하세요.");
        if (info.Length != full.IsoSize)
            throw new InvalidDataException(string.Format(CultureInfo.InvariantCulture,
                "ISO 크기가 다릅니다.\n필요: {0:N0}B\n현재: {1:N0}B\n" +
                "한국어화 v1.4.3s1 기준 ISO(srwogs-v1.4.3s1.iso)인지 확인하세요.",
                full.IsoSize, info.Length));

        log("현재 ISO 해시 확인 중…");
        string current = Sha256(isoPath, delegate(long d, long t)
        {
            if (progress != null) progress((int)(d * 50 / Math.Max(1, t)));
        });
        string dst = desiredHash;

        Pack pack = SelectFixedPlan(packs, option, oukaBase, oukaHidden, features, fix, current, selected);
        bool isPatched = string.Equals(current, dst, StringComparison.OrdinalIgnoreCase);
        bool isFull = current == Hex(full.SourceHash);

        log("  " + current);
        if (isPatched) log("  -> 이미 최신 패치가 적용된 상태입니다.");
        else if (pack != null && isFull) log("  -> 기준본(미적용) 상태입니다.");
        else if (pack != null) log("  -> 직전 릴리즈 적용본입니다. 핫픽스로 업그레이드합니다.");
        else log("  -> 기준본도 패치본도 아닙니다.");
        log(string.Empty);

        if (mode == Mode.Verify)
        {
            if (isPatched) log("검증 결과: 최신 패치 적용됨 (정상).");
            else if (pack != null && isFull) log("검증 결과: 기준본. 아직 적용되지 않았습니다.");
            else if (pack != null) log("검증 결과: 직전 릴리즈 적용본. [패치 적용]으로 업그레이드하세요.");
            else
            {
                throw new InvalidDataException("검증 결과: 지원하지 않는 ISO입니다.");
            }
            if (progress != null) progress(100);
            return;
        }

        if (isPatched)
        {
            log("이미 적용되어 있어 할 일이 없습니다.");
            if (progress != null) progress(100);
            return;
        }
        if (pack == null)
            throw new InvalidDataException(
                "적용할 수 있는 ISO 가 아닙니다.\n\n" +
                "이 패처는 한국어화 v1.4.3s1 기준 ISO" +
                (packs.Count > 1 ? " 또는 직전 릴리즈 적용본" : "") + "에만 적용됩니다.\n" +
                "기준 ISO SHA-256:\n" + Hex(full.SourceHash) + "\n" +
                "이미 다른 패치를 적용했다면 기준본을 다시 준비하세요.");

        string backupPath = isoPath + BackupExt;
        log("백업 생성: " + Path.GetFileName(backupPath));
        using (FileStream iso = new FileStream(isoPath, FileMode.Open, FileAccess.Read,
                                              FileShare.Read, 1 << 20))
        using (FileStream bak = new FileStream(backupPath, FileMode.Create,
                                              FileAccess.Write, FileShare.None, 1 << 20))
        using (BinaryWriter w = new BinaryWriter(bak))
        {
            w.Write(Encoding.ASCII.GetBytes(BackupMagic));
            w.Write(FormatVersion);
            w.Write(pack.IsoSize);
            w.Write(pack.SourceHash);
            w.Write(pack.Ranges.Count);
            byte[] buffer = new byte[1 << 20];
            for (int i = 0; i < pack.Ranges.Count; i++)
            {
                PatchRange range = pack.Ranges[i];
                iso.Seek(range.Offset, SeekOrigin.Begin);
                if (buffer.Length < range.Data.Length) buffer = new byte[range.Data.Length];
                int read = 0;
                while (read < range.Data.Length)
                {
                    int n = iso.Read(buffer, read, range.Data.Length - read);
                    if (n <= 0) throw new IOException("ISO 읽기 실패");
                    read += n;
                }
                w.Write(range.Offset);
                w.Write(range.Data.Length);
                w.Write(buffer, 0, range.Data.Length);
                if (progress != null) progress(50 + (int)(i * 20L / pack.Ranges.Count));
            }
        }

        log("구간 적용 중…");
        using (FileStream iso = new FileStream(isoPath, FileMode.Open, FileAccess.ReadWrite,
                                              FileShare.None, 1 << 20))
        {
            for (int i = 0; i < pack.Ranges.Count; i++)
            {
                PatchRange range = pack.Ranges[i];
                iso.Seek(range.Offset, SeekOrigin.Begin);
                iso.Write(range.Data, 0, range.Data.Length);
                if (progress != null) progress(70 + (int)(i * 15L / pack.Ranges.Count));
            }
            iso.Flush(true);
        }

        log("적용 후 해시 확인 중…");
        string after = Sha256(isoPath, delegate(long d, long t)
        {
            if (progress != null) progress(85 + (int)(d * 15 / Math.Max(1, t)));
        });
        log("  " + after);
        if (!string.Equals(after, dst, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException(
                "적용 후 해시가 기대값과 다릅니다.\n백업(" + BackupExt + ")으로 되돌리세요.");

        log(string.Empty);
        log("완료. 액셀 역할 교체 패치가 적용되었습니다.");
        log("이전 ISO 의 세이브 스테이트는 사용하지 말고, 에뮬레이터를 완전히");
        log("재시작한 뒤 게임 내 저장 데이터를 불러와 플레이하세요.");
        if (progress != null) progress(100);
    }

    private static void RestoreFromBackup(string isoPath, string backupPath,
                                          Action<string> log, Action<int> progress)
    {
        log("백업으로 되돌리기");
        string storedHash;
        using (FileStream bak = new FileStream(backupPath, FileMode.Open, FileAccess.Read,
                                              FileShare.Read, 1 << 20))
        using (BinaryReader r = new BinaryReader(bak))
        {
            string magic = Encoding.ASCII.GetString(r.ReadBytes(BackupMagic.Length));
            if (magic != BackupMagic)
                throw new InvalidDataException("백업 파일 형식이 올바르지 않습니다.");
            r.ReadInt32();
            long isoSize = r.ReadInt64();
            storedHash = Hex(r.ReadBytes(HashSize));
            int count = r.ReadInt32();

            FileInfo info = new FileInfo(isoPath);
            if (info.Length != isoSize)
                throw new InvalidDataException("ISO 크기가 백업과 다릅니다.");

            using (FileStream iso = new FileStream(isoPath, FileMode.Open,
                                                  FileAccess.ReadWrite, FileShare.None, 1 << 20))
            {
                for (int i = 0; i < count; i++)
                {
                    long off = r.ReadInt64();
                    int len = r.ReadInt32();
                    byte[] data = r.ReadBytes(len);
                    iso.Seek(off, SeekOrigin.Begin);
                    iso.Write(data, 0, len);
                    if (progress != null) progress((int)(i * 90L / count));
                }
                iso.Flush(true);
            }
        }
        log("해시 확인 중…");
        string after = Sha256(isoPath, null);
        log("  " + after);
        if (string.Equals(after, storedHash, StringComparison.OrdinalIgnoreCase))
            log("완료. 백업 시점 상태로 되돌렸습니다.");
        else
            log("경고: 백업 시점 해시와 다릅니다. ISO 를 다시 준비하는 것이 안전합니다.");
        if (progress != null) progress(100);
    }

    // ---------- GUI ----------

    private sealed class MainForm : Form
    {
        private readonly TextBox isoBox = new TextBox();
        private readonly TextBox logBox = new TextBox();
        private readonly ProgressBar bar = new ProgressBar();
        private readonly Button patchBtn = new Button();
        private readonly Button verifyBtn = new Button();
        private readonly Button restoreBtn = new Button();
        private readonly Button browse = new Button();
        private readonly CheckBox hiddenCheck = new CheckBox();
        private readonly CheckBox oukaCheck = new CheckBox();
        private readonly CheckBox rewardsCheck = new CheckBox();
        private readonly CheckBox enemyCheck = new CheckBox();
        private readonly CheckBox spiritsCheck = new CheckBox();
        private bool working;

        public MainForm(string initialIso)
        {
            Text = "슈퍼로봇대전 OGs 액셀 역할 교체 패처 " + VersionText;
            ClientSize = new Size(900, 780);
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox = false;
            BackColor = Color.FromArgb(242, 246, 250);
            StartPosition = FormStartPosition.CenterScreen;
            Font = new Font("맑은 고딕", 9F);
            AllowDrop = true;
            FormClosing += delegate(object sender, FormClosingEventArgs e) { if (working) e.Cancel = true; };
            Panel header = new Panel();
            header.SetBounds(0, 0, 900, 82);
            header.BackColor = Color.FromArgb(17, 55, 86);
            Controls.Add(header);
            Label title = new Label();
            title.Text = "OGs 액셀 역할 교체 패처";
            title.Font = new Font("맑은 고딕", 18F, FontStyle.Bold);
            title.ForeColor = Color.White;
            title.SetBounds(24, 12, 850, 36); header.Controls.Add(title);
            Label subtitle = new Label();
            subtitle.Text = "ISO 확인 → 옵션 선택 → 패치 적용 · " + VersionText;
            subtitle.ForeColor = Color.FromArgb(205, 226, 242);
            subtitle.SetBounds(27, 51, 850, 24); header.Controls.Add(subtitle);
            DragEnter += delegate(object s, DragEventArgs e)
            {
                e.Effect = !working && e.Data.GetDataPresent(DataFormats.FileDrop)
                    ? DragDropEffects.Copy : DragDropEffects.None;
            };
            DragDrop += delegate(object s, DragEventArgs e)
            {
                string[] files = (string[])e.Data.GetData(DataFormats.FileDrop);
                if (!working && files.Length > 0 && File.Exists(files[0])) isoBox.Text = files[0];
            };

            Label lbl = new Label();
            lbl.Text = "ISO 경로 (드래그 앤 드롭 가능)";
            lbl.SetBounds(22, 98, 650, 22);
            Controls.Add(lbl);

            isoBox.SetBounds(22, 126, 750, 28);
            isoBox.Text = initialIso ?? string.Empty;
            Controls.Add(isoBox);

            browse.Text = "찾기";
            browse.SetBounds(784, 125, 94, 30);
            browse.Click += delegate
            {
                using (OpenFileDialog dlg = new OpenFileDialog())
                {
                    dlg.Filter = "PS2 ISO (*.iso)|*.iso|모든 파일 (*.*)|*.*";
                    if (dlg.ShowDialog(this) == DialogResult.OK) isoBox.Text = dlg.FileName;
                }
            };
            Controls.Add(browse);

            GroupBox options = new GroupBox();
            options.Text = "패치 옵션"; options.SetBounds(22, 172, 856, 184);
            Controls.Add(options);
            hiddenCheck.Text = "숨겨진 요소 자동 습득 (OG2)";
            hiddenCheck.Font = new Font("맑은 고딕", 10F, FontStyle.Bold);
            hiddenCheck.SetBounds(18, 26, 402, 28); hiddenCheck.Checked = false;
            options.Controls.Add(hiddenCheck);
            oukaCheck.Text = "오우카 생존 + 젠가 밸런스";
            oukaCheck.Font = new Font("맑은 고딕", 10F, FontStyle.Bold);
            oukaCheck.SetBounds(430, 26, 405, 28); oukaCheck.Checked = false;
            options.Controls.Add(oukaCheck);
            rewardsCheck.Text = "자금 +20% · PP 2배";
            rewardsCheck.Font = new Font("맑은 고딕", 10F, FontStyle.Bold);
            rewardsCheck.SetBounds(18, 60, 402, 28); options.Controls.Add(rewardsCheck);
            enemyCheck.Text = "적 강화 (능력치 +5 · 기본 개조 +1단)";
            enemyCheck.Font = new Font("맑은 고딕", 10F, FontStyle.Bold);
            enemyCheck.SetBounds(430, 60, 405, 28); options.Controls.Add(enemyCheck);
            spiritsCheck.Text = "액셀·제오라 정신기 변경";
            spiritsCheck.Font = new Font("맑은 고딕", 10F, FontStyle.Bold);
            spiritsCheck.SetBounds(18, 94, 800, 28); options.Controls.Add(spiritsCheck);
            Label optionInfo = new Label();
            optionInfo.Text = "워단 생존·37화 삼식 지급·무명 보충은 기본 적용입니다. 다섯 옵션은 각각 선택할 수 있습니다.\n이미 받은 보유품·보상은 유지됩니다. 적 개조는 다음 시나리오의 적 생성 시부터 적용됩니다.";
            optionInfo.SetBounds(20, 132, 820, 42); options.Controls.Add(optionInfo);

            Label info = new Label();
            info.Text = "작업 직전 상태를 .ogsbak에 백업합니다. 적용 후 PCSX2를 새로 실행하고 게임 내 세이브를 불러오세요.";
            info.BackColor = Color.FromArgb(255, 248, 220);
            info.Padding = new Padding(12); info.SetBounds(22, 370, 856, 52); Controls.Add(info);

            patchBtn.Text = "패치 적용";
            patchBtn.SetBounds(22, 440, 180, 40);
            patchBtn.BackColor = Color.FromArgb(17, 55, 86); patchBtn.ForeColor = Color.White;
            patchBtn.Click += delegate { Start(Mode.Patch); };
            Controls.Add(patchBtn);

            verifyBtn.Text = "상태 확인";
            verifyBtn.SetBounds(216, 440, 140, 40);
            verifyBtn.Click += delegate { Start(Mode.Verify); };
            Controls.Add(verifyBtn);

            restoreBtn.Text = "백업으로 되돌리기";
            restoreBtn.SetBounds(370, 440, 190, 40);
            restoreBtn.Click += delegate { StartRestore(); };
            Controls.Add(restoreBtn);

            bar.SetBounds(22, 496, 856, 20);
            Controls.Add(bar);

            logBox.SetBounds(22, 532, 856, 226);
            logBox.Multiline = true;
            logBox.ReadOnly = true;
            logBox.ScrollBars = ScrollBars.Vertical;
            logBox.Font = new Font("Consolas", 9F);
            logBox.BackColor = Color.FromArgb(22, 28, 34);
            logBox.ForeColor = Color.FromArgb(224, 236, 244);
            Controls.Add(logBox);

            Log("한국어화 v1.4.3s1 기준 ISO 를 선택하고 [패치 적용]을 누르세요.");
            Log("기준본: srwogs-v1.4.3s1.iso (4,518,150,144바이트)");
            Log("적용 전 기준본 구간을 " + BackupExt + " 백업으로 남깁니다.");
            Log(string.Empty);
            Log("※ 이전 ISO 의 세이브 스테이트는 사용하지 마세요.");
            Log("※ 옵션은 코드 실행·분기 검증을 마쳤으며 전 루트 실플레이 검증은 별도입니다.");
        }

        private void Log(string text)
        {
            if (InvokeRequired) { BeginInvoke((Action<string>)Log, text); return; }
            logBox.AppendText(text + Environment.NewLine);
        }

        private void SetProgress(int value)
        {
            if (InvokeRequired) { BeginInvoke((Action<int>)SetProgress, value); return; }
            bar.Value = Math.Max(0, Math.Min(100, value));
        }

        private void SetBusy(bool busy)
        {
            if (InvokeRequired) { BeginInvoke((Action<bool>)SetBusy, busy); return; }
            working = busy;
            patchBtn.Enabled = verifyBtn.Enabled = restoreBtn.Enabled = !busy;
            rewardsCheck.Enabled = enemyCheck.Enabled = spiritsCheck.Enabled = oukaCheck.Enabled = hiddenCheck.Enabled = isoBox.Enabled = browse.Enabled = !busy;
        }

        private void Start(Mode mode)
        {
            string iso = isoBox.Text.Trim().Trim('"');
            if (iso.Length == 0) { MessageBox.Show(this, "ISO 를 선택하세요."); return; }
            SetBusy(true);
            SetProgress(0);
            logBox.Clear();
            bool hidden = hiddenCheck.Checked;
            bool ouka = oukaCheck.Checked;
            bool rewards = rewardsCheck.Checked, enemy = enemyCheck.Checked, spirits = spiritsCheck.Checked;
            Thread t = new Thread(delegate()
            {
                try { Run(iso, mode, hidden, ouka, rewards, enemy, spirits, Log, SetProgress); }
                catch (Exception ex) { Log(string.Empty); Log("오류: " + ex.Message); }
                finally { SetBusy(false); }
            });
            t.IsBackground = true;
            t.Start();
        }

        private void StartRestore()
        {
            string iso = isoBox.Text.Trim().Trim('"');
            if (iso.Length == 0) { MessageBox.Show(this, "ISO 를 선택하세요."); return; }
            string backup = iso + BackupExt;
            if (!File.Exists(backup))
            {
                using (OpenFileDialog dlg = new OpenFileDialog())
                {
                    dlg.Filter = "백업 (*" + BackupExt + ")|*" + BackupExt +
                                 "|모든 파일 (*.*)|*.*";
                    if (dlg.ShowDialog(this) != DialogResult.OK) return;
                    backup = dlg.FileName;
                }
            }
            SetBusy(true);
            SetProgress(0);
            logBox.Clear();
            string bk = backup;
            Thread t = new Thread(delegate()
            {
                try { RestoreFromBackup(iso, bk, Log, SetProgress); }
                catch (Exception ex) { Log(string.Empty); Log("오류: " + ex.Message); }
                finally { SetBusy(false); }
            });
            t.IsBackground = true;
            t.Start();
        }
    }

    // ---------- 진입점 ----------

    [STAThread]
    private static int Main(string[] args)
    {
        bool cli = false;
        bool selfTest = false;
        bool restore = false;
        bool hidden = false;
        bool ouka = false;
        bool rewards = false, enemy = false, spirits = false;
        string iso = null;
        Mode mode = Mode.Patch;
        for (int i = 0; i < args.Length; i++)
        {
            string a = args[i];
            if (a == "--self-test-options") { cli = true; selfTest = true; }
            else if (a == "--cli") cli = true;
            else if (a == "--verify") { cli = true; mode = Mode.Verify; }
            else if (a == "--restore") { cli = true; restore = true; }
            else if (a == "--hidden") hidden = true;
            else if (a == "--bundle" || a == "--ouka") ouka = true;
            else if (a == "--rewards") rewards = true;
            else if (a == "--enemy") enemy = true;
            else if (a == "--spirits") spirits = true;
            else if (iso == null) iso = a;
        }

        if (!cli)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new MainForm(iso));
            return 0;
        }

        AttachConsole(AttachParentProcess);
        try
        {
            if (selfTest) { CheckOptionTransitions(); return 0; }
            if (iso == null)
            {
                Console.WriteLine(
                    "사용: OGS_AxelSwap_QuickPatch.exe <ISO> [--cli|--verify|--restore] [--hidden] [--bundle] [--rewards] [--enemy] [--spirits]");
                return 2;
            }
            if (restore)
            {
                string backup = iso + BackupExt;
                if (!File.Exists(backup))
                    throw new FileNotFoundException("ISO 백업을 찾을 수 없습니다: " + backup);
                RestoreFromBackup(iso, backup, Console.WriteLine, null);
            }
            else
            {
                Run(iso, mode, hidden, ouka, rewards, enemy, spirits, Console.WriteLine, null);
            }
            return 0;
        }
        catch (Exception ex)
        {
            Console.WriteLine("오류: " + ex.Message);
            return 1;
        }
    }
}
