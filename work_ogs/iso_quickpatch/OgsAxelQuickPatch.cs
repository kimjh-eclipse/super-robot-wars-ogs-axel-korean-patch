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
    private const string VersionText = "v20260904";
    private const string PatchResourceName = "OGS_ISO_ranges.bin";
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
            pack.Ranges = new List<PatchRange>(count);
            long payload = 0;
            for (int i = 0; i < count; i++)
            {
                PatchRange range = new PatchRange();
                range.Offset = r.ReadInt64();
                int length = r.ReadInt32();
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

    private static void Run(string isoPath, Mode mode, Action<string> log,
                            Action<int> progress)
    {
        List<Pack> packs = LoadPacks();
        Pack full = packs[0];
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
        string dst = Hex(full.TargetHash);

        Pack pack = null;
        foreach (Pack p in packs)
        {
            if (string.Equals(current, Hex(p.SourceHash), StringComparison.OrdinalIgnoreCase))
            { pack = p; break; }
        }
        bool isPatched = string.Equals(current, dst, StringComparison.OrdinalIgnoreCase);
        bool isFull = pack == packs[0];

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
                log("검증 결과: 알 수 없는 ISO 입니다.");
                log("다른 패치가 적용되었거나 기준본이 아닐 수 있습니다.");
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

        public MainForm(string initialIso)
        {
            Text = "슈퍼로봇대전 OGs 액셀 역할 교체 패처 " + VersionText;
            Width = 760;
            Height = 560;
            StartPosition = FormStartPosition.CenterScreen;
            Font = new Font("맑은 고딕", 9F);
            AllowDrop = true;
            DragEnter += delegate(object s, DragEventArgs e)
            {
                e.Effect = e.Data.GetDataPresent(DataFormats.FileDrop)
                    ? DragDropEffects.Copy : DragDropEffects.None;
            };
            DragDrop += delegate(object s, DragEventArgs e)
            {
                string[] files = (string[])e.Data.GetData(DataFormats.FileDrop);
                if (files.Length > 0 && File.Exists(files[0])) isoBox.Text = files[0];
            };

            Label lbl = new Label();
            lbl.Text = "ISO 경로 (드래그 앤 드롭 가능)";
            lbl.SetBounds(12, 12, 300, 18);
            Controls.Add(lbl);

            isoBox.SetBounds(12, 32, 620, 24);
            isoBox.Text = initialIso ?? string.Empty;
            Controls.Add(isoBox);

            Button browse = new Button();
            browse.Text = "찾기";
            browse.SetBounds(640, 31, 90, 26);
            browse.Click += delegate
            {
                using (OpenFileDialog dlg = new OpenFileDialog())
                {
                    dlg.Filter = "PS2 ISO (*.iso)|*.iso|모든 파일 (*.*)|*.*";
                    if (dlg.ShowDialog(this) == DialogResult.OK) isoBox.Text = dlg.FileName;
                }
            };
            Controls.Add(browse);

            patchBtn.Text = "패치 적용";
            patchBtn.SetBounds(12, 68, 150, 34);
            patchBtn.Click += delegate { Start(Mode.Patch); };
            Controls.Add(patchBtn);

            verifyBtn.Text = "상태 확인";
            verifyBtn.SetBounds(172, 68, 120, 34);
            verifyBtn.Click += delegate { Start(Mode.Verify); };
            Controls.Add(verifyBtn);

            restoreBtn.Text = "백업으로 되돌리기";
            restoreBtn.SetBounds(302, 68, 160, 34);
            restoreBtn.Click += delegate { StartRestore(); };
            Controls.Add(restoreBtn);

            bar.SetBounds(12, 112, 718, 18);
            Controls.Add(bar);

            logBox.SetBounds(12, 140, 718, 360);
            logBox.Multiline = true;
            logBox.ReadOnly = true;
            logBox.ScrollBars = ScrollBars.Vertical;
            logBox.Font = new Font("Consolas", 9F);
            Controls.Add(logBox);

            Log("한국어화 v1.4.3s1 기준 ISO 를 선택하고 [패치 적용]을 누르세요.");
            Log("기준본: srwogs-v1.4.3s1.iso (4,518,150,144바이트)");
            Log("적용 전 기준본 구간을 " + BackupExt + " 백업으로 남깁니다.");
            Log(string.Empty);
            Log("※ 이전 ISO 의 세이브 스테이트는 사용하지 마세요.");
            Log("※ 정적 전수 검증 완료, 전 루트 실플레이 검증은 진행 중입니다.");
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
            patchBtn.Enabled = verifyBtn.Enabled = restoreBtn.Enabled = !busy;
        }

        private void Start(Mode mode)
        {
            string iso = isoBox.Text.Trim().Trim('"');
            if (iso.Length == 0) { MessageBox.Show(this, "ISO 를 선택하세요."); return; }
            SetBusy(true);
            SetProgress(0);
            logBox.Clear();
            Thread t = new Thread(delegate()
            {
                try { Run(iso, mode, Log, SetProgress); }
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
        bool restore = false;
        string iso = null;
        Mode mode = Mode.Patch;
        for (int i = 0; i < args.Length; i++)
        {
            string a = args[i];
            if (a == "--cli") cli = true;
            else if (a == "--verify") { cli = true; mode = Mode.Verify; }
            else if (a == "--restore") { cli = true; restore = true; }
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
            if (iso == null)
            {
                Console.WriteLine(
                    "사용: OGS_AxelSwap_QuickPatch.exe <ISO> [--cli|--verify|--restore]");
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
                Run(iso, mode, Console.WriteLine, null);
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
