# Mk-III Trombe coexistence local fix — 2026-11-19

- OG2 chapter 42 conversion (Trombe 0x4BA → Type R 0x4B9) now grants Type R without removing Trombe.
- Body and weapon upgrade grades are copied. Equipped parts and pilot records stay on their current unit; neither is duplicated.
- Existing saves after chapter 41 can restore a missing Trombe by opening the change-unit menu with Type R owned.
- Backfill preserves the existing Type R record and its grades, parts and pilot. Repeated menu/event calls do not duplicate units.
- OG1/OG2.5 helper calls and unrelated conversions preserve original behavior.
- Offline native-code checks passed; actual emulator play test remains for user.
- Applied only to local main/test ISOs. No release package was published.

Main ISO SHA256: `7c3db6581c03d16cf493605a7cdafc65e4df5cadd8e473beba6684fe83990241`
