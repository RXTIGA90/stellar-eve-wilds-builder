// Stellar Eve for Monster Hunter Wilds - installer window (language choice, outfit pictures, progress, uninstall).
// install.bat compiles this file on your PC with the C# compiler that ships with Windows (.NET Framework 4) into
// StellarEve.exe; no prebuilt program is downloaded. The actual work is install.ps1 (-NoGui), run hidden while this
// window shows its log and a percentage. C# 5 (the Windows compiler's language level): no string interpolation.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

static class App {
    public static string Root = Path.GetDirectoryName(Application.ExecutablePath);
    public static string Lang = "ko";
    public static bool NoInstall;   // --noinstall: build only, nothing goes into the game (testing)
    public static readonly Color Bg = Color.FromArgb(21, 23, 28), Panel = Color.FromArgb(31, 34, 41), Card = Color.FromArgb(38, 42, 51),
        CardOn = Color.FromArgb(24, 72, 52), Fg = Color.FromArgb(232, 234, 237), Sub = Color.FromArgb(154, 160, 166),
        Accent = Color.FromArgb(43, 214, 123), Dlc = Color.FromArgb(255, 169, 77), Bad = Color.FromArgb(255, 107, 107), Track = Color.FromArgb(48, 52, 62);

    static readonly Dictionary<string, string[]> S = new Dictionary<string, string[]> {
        {"lang_title", new[] {"언어를 고르세요", "Choose your language"}},
        {"home_sub", new[] {"내 스텔라 블레이드와 몬헌 와일즈 파일로 이브를 만들어 넣습니다. 게임 파일은 포함되어 있지 않습니다.",
                            "Builds Eve from your own Stellar Blade and Monster Hunter Wilds files. No game files are included."}},
        {"home_install", new[] {"설치 / 의상 추가", "Install / add outfits"}},
        {"home_install_d", new[] {"의상을 사진으로 보고 골라 설치합니다. 이미 넣은 의상은 그대로 남습니다.\n처음에는 도구(약 1GB)를 받고, 의상 1벌당 약 2분 걸립니다.",
                                  "Pick outfits by their pictures and install them. Outfits installed before stay.\nThe first run downloads tools (about 1 GB); each outfit takes about 2 minutes."}},
        {"home_uninstall", new[] {"제거 (게임을 원래대로)", "Uninstall (restore the game)"}},
        {"home_uninstall_d", new[] {"이 설치기가 넣은 파일을 모두 빼고 바뀐 원본을 되돌립니다. 바로가기도 지웁니다.\n그다음 이 폴더를 지우면 완전히 정리됩니다. 몬헌 세이브 데이터는 건드리지 않습니다.",
                                    "Removes every file this installer put in and puts back any original it replaced, and removes the shortcuts.\nAfterwards you can delete this folder. Your Monster Hunter save data is not touched."}},
        {"home_readme", new[] {"설명서 (README)", "Guide (README)"}},
        {"home_lang", new[] {"Language / 언어", "언어 / Language"}},
        {"pick_title", new[] {"설치할 의상 고르기", "Choose outfits"}},
        {"pick_sub", new[] {"설치할 의상에 체크하세요(사진을 눌러도 됩니다). 이브 얼굴은 항상 포함됩니다.\n게임에서는 카드에 적힌 몬헌 갑옷을 외형(덧입기)으로 입으면 그 의상이 나옵니다. 그 갑옷을 게임에서 만들어 둬야 목록에 나옵니다.",
                            "Tick the outfits to install (clicking a picture works too). Eve's face is always included.\nIn game, wear the Wilds armor written on the card as layered appearance to see the outfit. The armor has to be crafted to show up."}},
        {"pick_armor", new[] {"몬헌 갑옷", "Wilds armor"}},
        {"pick_eve", new[] {"스텔라 블레이드", "Stellar Blade"}},
        {"pick_dlc", new[] {"DLC 필요", "needs the DLC"}},
        {"pick_jobs", new[] {"동시 빌드", "Build at once"}},
        {"pick_shortcut", new[] {"바탕화면·시작 메뉴 바로가기", "Desktop + Start menu shortcut"}},
        {"pick_count", new[] {"{0}개 선택", "{0} selected"}},
        {"pick_all", new[] {"전체 선택", "Select all"}},
        {"pick_clear", new[] {"전체 해제", "Clear"}},
        {"pick_back", new[] {"뒤로", "Back"}},
        {"pick_install", new[] {"설치", "Install"}},
        {"pick_none", new[] {"의상을 하나 이상 고르세요.", "Tick at least one outfit."}},
        {"nopreview", new[] {"미리보기 없음", "no preview"}},
        {"game_running", new[] {"몬스터 헌터 와일즈가 켜져 있습니다. 게임을 끄고 다시 눌러 주세요.", "Monster Hunter Wilds is running. Close the game and try again."}},
        {"prog_title", new[] {"설치 중", "Installing"}},
        {"prog_sub", new[] {"내 게임 파일로 이브를 만드는 중입니다. 몬헌은 끈 상태로 두세요.", "Building Eve from your own games. Keep Monster Hunter Wilds closed."}},
        {"st_start", new[] {"시작하는 중", "Starting"}},
        {"st_tools", new[] {"도구 받는 중 ({0}/9)", "Downloading tools ({0}/9)"}},
        {"st_prep", new[] {"게임에서 이브 파일 꺼내는 중", "Taking Eve's files out of the games"}},
        {"st_base", new[] {"이브 얼굴·기본 외형 만드는 중", "Building Eve's face and default looks"}},
        {"st_outfits", new[] {"의상 만드는 중 ({0}/{1})", "Building outfits ({0}/{1})"}},
        {"st_inst", new[] {"게임에 설치하는 중", "Installing into the game"}},
        {"st_done", new[] {"완료! 게임을 켜세요.", "Done! Start the game."}},
        {"st_fail", new[] {"오류로 멈췄습니다", "Stopped with an error"}},
        {"st_cancel", new[] {"취소했습니다", "Cancelled"}},
        {"detail", new[] {"경과 {0}   ·   의상 {1}벌   ·   동시 {2}", "Elapsed {0}   ·   {1} outfits   ·   {2} at once"}},
        {"took", new[] {"걸린 시간 {0}   ·   제거는 이 프로그램의 '제거'", "Took {0}   ·   to remove: 'Uninstall' in this program"}},
        {"btn_cancel", new[] {"취소", "Cancel"}},
        {"btn_close", new[] {"닫기", "Close"}},
        {"btn_log", new[] {"로그 열기", "Open log"}},
        {"ask_stop", new[] {"설치를 멈출까요?", "Stop the installation?"}},
        {"un_title", new[] {"제거", "Uninstall"}},
        {"un_ask", new[] {"이 설치기가 몬헌에 넣은 이브 파일을 모두 빼고, 바뀐 원본을 되돌립니다.\n바탕화면·시작 메뉴 바로가기도 지웁니다. 세이브 데이터는 건드리지 않습니다.\n\n제거할까요?",
                          "This removes every Eve file this installer put into Monster Hunter Wilds and puts back any original it replaced.\nThe desktop and Start menu shortcuts are removed too. Save data is not touched.\n\nUninstall now?"}},
        {"un_sub", new[] {"게임을 설치 전 상태로 되돌리는 중입니다.", "Putting the game back as it was."}},
        {"un_running", new[] {"제거하는 중", "Uninstalling"}},
        {"un_done", new[] {"제거 완료! 게임이 원래대로 돌아왔습니다.", "Uninstalled. The game is back as it was."}},
        {"un_done_d", new[] {"이제 이 폴더({0})를 지워도 됩니다.", "You can now delete this folder ({0})."}},
        {"un_nothing", new[] {"이 폴더로 설치한 기록이 없습니다(설치를 안 했거나 이미 제거됨).", "Nothing was installed from this folder (never installed, or already removed)."}},
        {"ck_title", new[] {"설치 전 점검", "Before you install"}},
        {"ck_mhw_ok", new[] {"몬스터 헌터 와일즈: {0}", "Monster Hunter Wilds: {0}"}},
        {"ck_mhw_no", new[] {"몬스터 헌터 와일즈를 찾지 못했습니다. Steam으로 설치했다면 [폴더 선택]으로 MonsterHunterWilds.exe가 있는 폴더를 고르세요.",
                             "Monster Hunter Wilds not found. If it is installed, press [Choose folder] and pick the folder with MonsterHunterWilds.exe."}},
        {"ck_ref_ok", new[] {"REFramework: 설치됨 (dinput8.dll)", "REFramework: installed (dinput8.dll)"}},
        {"ck_ref_no", new[] {"REFramework가 없습니다. 없으면 게임에서 이브 얼굴·체형이 적용되지 않습니다. [받는 곳]에서 REFramework.zip을 받아 dinput8.dll을 몬헌 폴더에 넣으세요.",
                             "REFramework is missing: without it Eve's face and body do not apply in game. [Download page]: get REFramework.zip and put dinput8.dll in the Monster Hunter Wilds folder."}},
        {"ck_sb_ok", new[] {"스텔라 블레이드: {0}", "Stellar Blade: {0}"}},
        {"ck_sb_no", new[] {"스텔라 블레이드를 찾지 못했습니다. 이브 파일은 스텔라 블레이드에서 가져오므로 꼭 필요합니다. 설치했다면 [폴더 선택]으로 StellarBlade 폴더를 고르세요.",
                            "Stellar Blade not found. Eve's files come from it, so it is required. If it is installed, press [Choose folder] and pick the StellarBlade folder."}},
        {"ck_disk_ok", new[] {"빈 공간: {0} GB (필요 약 {1} GB)", "Free space: {0} GB (about {1} GB needed)"}},
        {"ck_disk_no", new[] {"빈 공간이 부족합니다: {0} GB (필요 약 {1} GB). 다른 드라이브에 폴더를 옮기거나 공간을 비우세요.",
                              "Not enough free space: {0} GB (about {1} GB needed). Move this folder to another drive or free some space."}},
        {"ck_path_ok", new[] {"설치 폴더: {0}", "Install folder: {0}"}},
        {"ck_path_no", new[] {"폴더 경로에 한글이나 공백이 있습니다: {0}  ·  도구가 실패할 수 있으니 D:\\stellar-eve 같은 영어 경로로 옮기는 것을 권장합니다.",
                              "The folder path has spaces or non-English characters: {0}  ·  some tools may fail; moving it to a plain path like D:\\stellar-eve is recommended."}},
        {"ck_browse", new[] {"폴더 선택", "Choose folder"}},
        {"ck_get", new[] {"받는 곳", "Download page"}},
        {"ck_recheck", new[] {"다시 점검", "Check again"}},
        {"ck_pick_mhw", new[] {"MonsterHunterWilds.exe가 있는 폴더를 고르세요", "Pick the folder that has MonsterHunterWilds.exe"}},
        {"ck_pick_sb", new[] {"StellarBlade 폴더를 고르세요 (그 안에 SB\\Content\\Paks가 있는 폴더)", "Pick the StellarBlade folder (the one with SB\\Content\\Paks inside)"}},
        {"ck_bad_pick", new[] {"이 폴더에는 필요한 파일이 없습니다:\n{0}", "This folder does not have the needed file:\n{0}"}},
        {"ck_block", new[] {"설치할 수 없습니다. 빨간색 항목을 먼저 해결하세요:\n\n{0}", "Cannot install yet. Fix the red items first:\n\n{0}"}},
        {"ck_warn", new[] {"주의할 항목이 있습니다:\n\n{0}\n\n그래도 계속할까요?", "Some items need attention:\n\n{0}\n\nContinue anyway?"}},
        {"err_open", new[] {"설치 창을 열 수 없습니다: {0}\n글자 화면 설치(install.bat -NoGui)로 진행해 주세요.", "The installer window could not open: {0}\nUse the text installer instead (install.bat -NoGui)."}},
    };
    public static string T(string k) { string[] v; return S.TryGetValue(k, out v) ? v[Lang == "en" ? 1 : 0] : k; }

    public static Font F(float size, bool bold = false) { return new Font("Malgun Gothic", size, bold ? FontStyle.Bold : FontStyle.Regular); }
    public static Icon AppIcon() { try { return Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { return null; } }
    public static Image LoadImage(string path) {
        if (!File.Exists(path)) return null;
        using (var ms = new MemoryStream(File.ReadAllBytes(path))) return new Bitmap(Image.FromStream(ms));
    }
    public static Form NewForm(string title, int w, int h) {
        var f = new Form { Text = "Stellar Eve - " + title, BackColor = Bg, ForeColor = Fg, Font = F(9), Icon = AppIcon(), StartPosition = FormStartPosition.Manual };
        var wa = Screen.FromPoint(Cursor.Position).WorkingArea;   // fits a small or portrait screen
        f.Size = new Size(Math.Min(w, wa.Width - 40), Math.Min(h, wa.Height - 40));
        f.Location = new Point(wa.X + (wa.Width - f.Width) / 2, wa.Y + (wa.Height - f.Height) / 2);
        return f;
    }
    // started from Explorer the window can open behind it: lift it to the front once when it appears
    public static void Front(Form f) { f.Shown += (s, e) => { f.TopMost = true; f.Activate(); f.TopMost = false; }; }
    public static Panel Header(string sub) {
        var p = new Panel { Dock = DockStyle.Top, Height = 104, BackColor = Panel };
        var img = LoadImage(Path.Combine(Root, @"data\ui\header.png"));
        if (img != null) p.Controls.Add(new PictureBox { Image = img, SizeMode = PictureBoxSizeMode.Zoom, Location = new Point(14, 10), Size = new Size(84, 84) });
        p.Controls.Add(new Label { Text = "Stellar Eve for Monster Hunter Wilds", Font = F(16, true), ForeColor = Fg, AutoSize = true, Location = new Point(110, 14) });
        p.Controls.Add(new Label { Text = sub, ForeColor = Sub, AutoSize = true, Location = new Point(112, 54), MaximumSize = new Size(1100, 48) });
        return p;
    }
    public static Button Btn(string text, int w, bool primary = false) {
        var b = new Button { Text = text, Size = new Size(w, 36), FlatStyle = FlatStyle.Flat, Cursor = Cursors.Hand, Margin = new Padding(6, 0, 0, 0) };
        if (primary) { b.BackColor = Accent; b.ForeColor = Color.FromArgb(10, 30, 20); b.Font = F(10, true); b.FlatAppearance.BorderSize = 0; }
        else { b.BackColor = Card; b.ForeColor = Fg; b.FlatAppearance.BorderColor = Track; }
        return b;
    }
    public static bool GameRunning() { return !NoInstall && Process.GetProcessesByName("MonsterHunterWilds").Length > 0; }
    // launcher_settings.txt: line 1 = language, then mhw=<folder> / sb=<folder> when picked by hand
    static string SettingsFile { get { return Path.Combine(Root, "launcher_settings.txt"); } }
    public static string MhwPick = "", SbPick = "";
    public static void LoadSettings() {
        try {
            foreach (var raw in File.ReadAllLines(SettingsFile, Encoding.UTF8)) {
                var t = raw.Trim();
                if (t == "en" || t == "ko") Lang = t;
                else if (t.StartsWith("mhw=")) MhwPick = t.Substring(4);
                else if (t.StartsWith("sb=")) SbPick = t.Substring(3);
            }
        } catch { }
    }
    public static void SaveSettings() { try { File.WriteAllText(SettingsFile, Lang + "\r\nmhw=" + MhwPick + "\r\nsb=" + SbPick + "\r\n", Encoding.UTF8); } catch { } }

    [System.Runtime.InteropServices.DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [System.Runtime.InteropServices.DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int cmd);
    [STAThread]
    static void Main(string[] args) {
        // one window per folder: clicking install.bat / the shortcut again brings the open window to the front
        bool first;
        using (var one = new Mutex(true, @"Local\StellarEve_" + Root.ToLowerInvariant().Replace('\\', '/'), out first)) {
            if (!first) { FocusOther(); return; }
            Run(args);
        }
    }
    static void FocusOther() {
        var me = Process.GetCurrentProcess();
        foreach (var p in Process.GetProcessesByName(me.ProcessName)) {
            if (p.Id == me.Id || p.MainWindowHandle == IntPtr.Zero) continue;
            ShowWindow(p.MainWindowHandle, 9); SetForegroundWindow(p.MainWindowHandle); break;   // 9 = restore if minimized
        }
    }
    static void Run(string[] args) {
        Application.EnableVisualStyles(); Application.SetCompatibleTextRenderingDefault(false);
        try {
            LoadSettings();
            int jobs = 0; bool uninstall = false;
            for (int i = 0; i < args.Length; i++) {
                var a = args[i].ToLowerInvariant();
                if (a == "--uninstall" || a == "-uninstall") uninstall = true;
                else if (a == "--noinstall" || a == "-noinstall") NoInstall = true;
                else if ((a == "-jobs" || a == "--jobs") && i + 1 < args.Length) int.TryParse(args[++i], out jobs);
                else if ((a == "--lang" || a == "-lang") && i + 1 < args.Length) Lang = args[++i] == "en" ? "en" : "ko";
            }
            if (!new LanguageForm().Choose()) return;
            SaveSettings();
            if (uninstall) { Flows.Uninstall(); return; }
            new HomeForm(jobs).ShowDialog();
        } catch (Exception e) {
            MessageBox.Show(string.Format(T("err_open"), e.Message), "Stellar Eve");
        }
    }
}

class LanguageForm : Form {
    bool chosen;
    public LanguageForm() {
        var f = App.NewForm("Language / 언어", 560, 380); Text = f.Text; BackColor = f.BackColor; ForeColor = f.ForeColor; Font = f.Font; Icon = f.Icon; App.Front(this);
        Size = f.Size; StartPosition = FormStartPosition.Manual; Location = f.Location; FormBorderStyle = FormBorderStyle.FixedSingle; MaximizeBox = false;
        Controls.Add(App.Header("언어를 고르세요  /  Choose your language"));
        var ko = App.Btn("한국어", 220, App.Lang == "ko"); var en = App.Btn("English", 220, App.Lang == "en");
        ko.Size = en.Size = new Size(220, 90); ko.Font = en.Font = App.F(16, true);
        ko.Location = new Point(40, 150); en.Location = new Point(290, 150);
        ko.Click += delegate { App.Lang = "ko"; chosen = true; Close(); };
        en.Click += delegate { App.Lang = "en"; chosen = true; Close(); };
        Controls.Add(ko); Controls.Add(en);
        Controls.Add(new Label { Text = "설치·제거 화면과 의상·갑옷 이름이 고른 언어로 나옵니다.\nScreens and outfit / armor names follow the language you pick.", ForeColor = App.Sub, AutoSize = true, Location = new Point(40, 262) });
        AcceptButton = App.Lang == "en" ? en : ko;
    }
    public bool Choose() { ShowDialog(); return chosen; }
}

class HomeForm : Form {
    public HomeForm(int jobs) {
        var f = App.NewForm("Stellar Eve", 900, 740); Text = f.Text; BackColor = f.BackColor; ForeColor = f.ForeColor; Font = f.Font; Icon = f.Icon; App.Front(this);
        Size = f.Size; StartPosition = FormStartPosition.Manual; Location = f.Location; AutoScroll = true;
        Controls.Add(App.Header(App.T("home_sub")));
        Func<string, string, bool, int, Button> option = (title, desc, primary, y) => {
            var b = App.Btn(title, 0, primary); b.Size = new Size(260, 70); b.Font = App.F(12, true); b.Location = new Point(28, y);
            Controls.Add(b);
            Controls.Add(new Label { Text = desc, ForeColor = App.Sub, Location = new Point(306, y + 4), Size = new Size(560, 66) });
            return b;
        };
        var inst = option(App.T("home_install"), App.T("home_install_d"), true, 132);
        var un = option(App.T("home_uninstall"), App.T("home_uninstall_d"), false, 222);
        var readme = App.Btn(App.T("home_readme"), 200); readme.Location = new Point(28, 320); Controls.Add(readme);
        var lang = App.Btn(App.T("home_lang"), 160); lang.Location = new Point(240, 320); Controls.Add(lang);
        checks = new Panel { Location = new Point(28, 374), Size = new Size(830, 300), BackColor = App.Panel };
        Controls.Add(checks); ShowChecks();
        inst.Click += delegate { Hide(); Flows.Install(jobs); ShowChecks(); Show(); };
        un.Click += delegate { Hide(); Flows.Uninstall(); ShowChecks(); Show(); };
        readme.Click += delegate {
            var p = Path.Combine(App.Root, App.Lang == "en" ? "README.md" : "README.ko.md");
            try { Process.Start("notepad.exe", "\"" + p + "\""); } catch { }
        };
        lang.Click += delegate { App.Lang = App.Lang == "en" ? "ko" : "en"; App.SaveSettings(); Hide(); new HomeForm(jobs).ShowDialog(); Close(); };
    }
    Panel checks;
    // "before you install" list: green = ok, orange = works but needs attention, red = install is blocked
    void ShowChecks() {
        checks.SuspendLayout(); checks.Controls.Clear();
        checks.Controls.Add(new Label { Text = App.T("ck_title"), Font = App.F(11, true), ForeColor = App.Fg, AutoSize = true, Location = new Point(14, 10) });
        var again = App.Btn(App.T("ck_recheck"), 110); again.Height = 28; again.Location = new Point(checks.Width - 124, 8);
        again.Click += delegate { ShowChecks(); };
        checks.Controls.Add(again);
        int y = 44;
        foreach (var c in Checks.Run()) {
            var col = c.Level == 0 ? App.Accent : c.Level == 1 ? App.Dlc : App.Bad;
            checks.Controls.Add(new Label { Text = c.Level == 0 ? "✔" : c.Level == 1 ? "!" : "✖", ForeColor = col, Font = App.F(11, true), Location = new Point(14, y - 2), Size = new Size(22, 24) });
            int w = c.Action == null ? 770 : 640;
            var t = new Label { Text = c.Text, ForeColor = c.Level == 0 ? App.Sub : col, Location = new Point(40, y), MaximumSize = new Size(w, 0), AutoSize = true };
            checks.Controls.Add(t);
            if (c.Action != null) {
                var b = App.Btn(App.T(c.Action == "ref" ? "ck_get" : "ck_browse"), 120); b.Height = 28; b.Location = new Point(checks.Width - 134, y - 4);
                var act = c.Action;
                b.Click += delegate { Act(act); };
                checks.Controls.Add(b);
            }
            y += Math.Max(t.PreferredHeight, 22) + 12;
        }
        checks.Height = y + 6;
        checks.ResumeLayout();
    }
    void Act(string act) {
        if (act == "ref") { try { Process.Start(Checks.RefUrl); } catch { } return; }
        using (var dlg = new FolderBrowserDialog { Description = App.T(act == "mhw" ? "ck_pick_mhw" : "ck_pick_sb"), ShowNewFolderButton = false }) {
            if (dlg.ShowDialog(this) != DialogResult.OK) return;
            var must = act == "mhw" ? Checks.MhwMust : Checks.SbMust;
            var dir = Checks.Normalize(dlg.SelectedPath, must);
            if (dir == "") { MessageBox.Show(string.Format(App.T("ck_bad_pick"), must), "Stellar Eve"); return; }
            if (act == "mhw") App.MhwPick = dir; else App.SbPick = dir;
            App.SaveSettings(); ShowChecks();
        }
    }
}

class Check { public int Level; public string Text, Action; }   // Level 0 ok, 1 warning, 2 missing (blocks install)

// what the install needs on this PC; same game search as install.ps1 (Steam registry, library folders, usual folder names)
static class Checks {
    public const string MhwMust = "MonsterHunterWilds.exe", SbMust = @"SB\Content\Paks\pakchunk0-WindowsNoEditor.pak";
    public static string MhwDir = "", SbDir = "";
    public const string RefUrl = "https://github.com/praydog/REFramework-nightly/releases";
    static bool Has(string dir, string must) { try { return dir != "" && File.Exists(Path.Combine(dir, must)); } catch { return false; } }
    static string FindSteam(string folder, string must) {
        var steams = new List<string>();
        foreach (var k in new[] { new[] { @"HKEY_CURRENT_USER\Software\Valve\Steam", "SteamPath" },
                                  new[] { @"HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath" },
                                  new[] { @"HKEY_LOCAL_MACHINE\SOFTWARE\Valve\Steam", "InstallPath" } }) {
            try { var v = Microsoft.Win32.Registry.GetValue(k[0], k[1], null) as string; if (!string.IsNullOrEmpty(v)) steams.Add(v.Replace('/', '\\')); } catch { }
        }
        steams.Add(@"C:\Program Files (x86)\Steam");
        var libs = new List<string>();
        foreach (var s in steams) {
            libs.Add(s);
            try {
                var vdf = Path.Combine(s, @"steamapps\libraryfolders.vdf");
                if (File.Exists(vdf)) foreach (Match m in Regex.Matches(File.ReadAllText(vdf), "\"path\"\\s+\"([^\"]+)\"")) libs.Add(m.Groups[1].Value.Replace(@"\\", @"\"));
            } catch { }
        }
        foreach (var d in DriveInfo.GetDrives()) {
            if (d.DriveType != DriveType.Fixed || !d.IsReady) continue;
            foreach (var sub in new[] { "SteamLibrary", "Steam", @"Program Files (x86)\Steam", @"Games\Steam", @"Games\SteamLibrary" }) libs.Add(Path.Combine(d.RootDirectory.FullName, sub));
        }
        foreach (var l in libs.Distinct(StringComparer.OrdinalIgnoreCase)) {
            var p = Path.Combine(l, @"steamapps\common\" + folder);
            if (Has(p, must)) return p;
        }
        return "";
    }
    // a folder the user picked: accept the game folder itself or one of the folders inside it
    public static string Normalize(string picked, string must) {
        for (var d = picked; !string.IsNullOrEmpty(d); d = Path.GetDirectoryName(d)) if (Has(d, must)) return d;
        return "";
    }
    public static List<Check> Run() {
        MhwDir = Has(App.MhwPick, MhwMust) ? App.MhwPick : FindSteam("MonsterHunterWilds", MhwMust);
        SbDir = Has(App.SbPick, SbMust) ? App.SbPick : FindSteam("StellarBlade", SbMust);
        var r = new List<Check>();
        r.Add(MhwDir != "" ? new Check { Text = string.Format(App.T("ck_mhw_ok"), MhwDir) } : new Check { Level = 2, Text = App.T("ck_mhw_no"), Action = "mhw" });
        if (MhwDir != "") r.Add(Has(MhwDir, "dinput8.dll") ? new Check { Text = App.T("ck_ref_ok") } : new Check { Level = 1, Text = App.T("ck_ref_no"), Action = "ref" });
        r.Add(SbDir != "" ? new Check { Text = string.Format(App.T("ck_sb_ok"), SbDir) } : new Check { Level = 2, Text = App.T("ck_sb_no"), Action = "sb" });
        try {
            // first run: tools (~3 GB) + extracted game files + builds; later runs reuse them
            int need = File.Exists(Path.Combine(App.Root, @"tools\blender\blender.exe")) ? 8 : 25;
            long free = new DriveInfo(Path.GetPathRoot(App.Root)).AvailableFreeSpace / (1L << 30);
            r.Add(new Check { Level = free < need ? 1 : 0, Text = string.Format(App.T(free < need ? "ck_disk_no" : "ck_disk_ok"), free, need) });
        } catch { }
        bool plain = App.Root.All(c => c < 128 && c != ' ');
        r.Add(new Check { Level = plain ? 0 : 1, Text = string.Format(App.T(plain ? "ck_path_ok" : "ck_path_no"), App.Root) });
        return r;
    }
    // the folders found here go to install.ps1, so a folder picked by hand is used there too
    public static string Args() {
        var a = "";
        if (MhwDir != "") a += " -MhwDir \"" + MhwDir.TrimEnd('\\') + "\"";
        if (SbDir != "") a += " -SbPaks \"" + Path.Combine(SbDir, @"SB\Content\Paks") + "\"";
        return a;
    }
    // before installing: red items stop it, warnings ask
    public static bool ReadyToInstall() {
        var cs = Run();
        var bad = cs.Where(c => c.Level == 2).Select(c => "• " + c.Text).ToArray();
        if (bad.Length > 0) { MessageBox.Show(string.Format(App.T("ck_block"), string.Join("\n\n", bad)), "Stellar Eve", MessageBoxButtons.OK, MessageBoxIcon.Warning); return false; }
        var warn = cs.Where(c => c.Level == 1).Select(c => "• " + c.Text).ToArray();
        return warn.Length == 0 || MessageBox.Show(string.Format(App.T("ck_warn"), string.Join("\n\n", warn)), "Stellar Eve", MessageBoxButtons.YesNo, MessageBoxIcon.Warning) == DialogResult.Yes;
    }
}

class Outfit {
    public string id { get; set; } public string eve_ko { get; set; } public string eve_en { get; set; } public string armor_ko { get; set; } public string armor_en { get; set; }
    public string where_ko { get; set; } public string where_en { get; set; } public string dlc { get; set; } public string note_ko { get; set; } public string note_en { get; set; }
    public bool default_look { get; set; }
}

static class Flows {
    public static List<Outfit> LoadOutfits() {
        var json = File.ReadAllText(Path.Combine(App.Root, @"data\outfit_names.json"), Encoding.UTF8);
        return new JavaScriptSerializer().Deserialize<List<Outfit>>(json);
    }
    static bool Built(string id, string joints) {
        return File.Exists(Path.Combine(App.Root, @"work\base" + id + @"-build\stage\reframework\data\stellar-eve\" + joints));
    }
    public static void Install(int jobsArg) {
        if (App.GameRunning()) { MessageBox.Show(App.T("game_running"), "Stellar Eve"); return; }
        if (!Checks.ReadyToInstall()) return;
        var outfits = LoadOutfits();
        int threads = Environment.ProcessorCount;
        int def = jobsArg > 0 ? jobsArg : threads >= 16 ? 3 : threads >= 8 ? 2 : 1;
        var pick = new PickerForm(outfits, Math.Min(4, def));
        if (!pick.Run()) return;
        if (pick.Shortcut) { try { Shortcuts.Create(); } catch { } }
        var sel = pick.Selected;
        bool all = sel.Count == outfits.Count;
        var args = "-Jobs " + pick.Jobs + (all ? " -All" : " -Rows " + string.Join(",", sel.ToArray())) + (App.NoInstall ? " -NoInstall" : "") + Checks.Args();
        // what the build will do, for the percentage (same rules as scripts/build_all.py)
        var plan = new Plan {
            tools = !File.Exists(Path.Combine(App.Root, @"tools\blender\blender.exe")),
            prepare = !File.Exists(Path.Combine(App.Root, @"work\sb_pc_list.txt")),
            bases = all ? 2 : (Built("27", "ocean_maid_joints.json") ? 0 : 1) + (sel.Contains("63") && !Built("63", "wave_bikini_joints.json") ? 1 : 0),
            outfits = sel.Count(s => s != "27" && s != "63"), jobs = pick.Jobs };
        new ProgressForm(App.T("prog_title"), App.T("prog_sub"), args, plan, false).ShowDialog();
    }
    public static void Uninstall() {
        if (App.GameRunning()) { MessageBox.Show(App.T("game_running"), "Stellar Eve"); return; }
        if (MessageBox.Show(App.T("un_ask"), "Stellar Eve - " + App.T("un_title"), MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return;
        try { Shortcuts.Remove(); } catch { }
        var added = Path.Combine(App.Root, @"work\game-backup\added.txt");
        if (!File.Exists(added) || !File.Exists(Path.Combine(App.Root, @"tools\blender\5.2\python\bin\python.exe"))) { MessageBox.Show(App.T("un_nothing"), "Stellar Eve"); return; }
        Checks.Run();
        new ProgressForm(App.T("un_title"), App.T("un_sub"), "-Uninstall" + Checks.Args(), null, true).ShowDialog();
    }
}

static class Shortcuts {
    static string MenuDir { get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Stellar Eve"); } }
    static string Desk { get { return Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "Stellar Eve.lnk"); } }
    static void Make(string path, string args, string desc) {
        var t = Type.GetTypeFromProgID("WScript.Shell"); dynamic sh = Activator.CreateInstance(t);
        dynamic l = sh.CreateShortcut(path);
        l.TargetPath = Application.ExecutablePath; l.Arguments = args; l.WorkingDirectory = App.Root; l.Description = desc;
        l.IconLocation = Application.ExecutablePath + ",0"; l.Save();
    }
    public static void Create() {
        Directory.CreateDirectory(MenuDir);
        Make(Desk, "", "Stellar Eve for Monster Hunter Wilds - install / add outfits / uninstall");
        Make(Path.Combine(MenuDir, "Stellar Eve.lnk"), "", "Stellar Eve for Monster Hunter Wilds - install / add outfits / uninstall");
        string un = App.Lang == "en" ? "Stellar Eve uninstall.lnk" : "Stellar Eve 제거.lnk", old = App.Lang == "en" ? "Stellar Eve 제거.lnk" : "Stellar Eve uninstall.lnk";
        Make(Path.Combine(MenuDir, un), "--uninstall", "Stellar Eve - restore the game");
        try { File.Delete(Path.Combine(MenuDir, old)); } catch { }   // the one made in the other language
    }
    public static void Remove() {
        // only shortcuts that point to this folder's StellarEve.exe
        var t = Type.GetTypeFromProgID("WScript.Shell"); dynamic sh = Activator.CreateInstance(t);
        var files = new List<string> { Desk };
        if (Directory.Exists(MenuDir)) files.AddRange(Directory.GetFiles(MenuDir, "*.lnk"));
        foreach (var f in files) {
            if (!File.Exists(f)) continue;
            dynamic l = sh.CreateShortcut(f);
            if (string.Equals((string)l.TargetPath, Application.ExecutablePath, StringComparison.OrdinalIgnoreCase)) File.Delete(f);
        }
        if (Directory.Exists(MenuDir) && Directory.GetFileSystemEntries(MenuDir).Length == 0) Directory.Delete(MenuDir);
    }
}

class PickerForm : Form {
    public List<string> Selected = new List<string>(); public int Jobs; public bool Shortcut; bool ok;
    readonly List<CheckBox> boxes = new List<CheckBox>();
    public PickerForm(List<Outfit> outfits, int defJobs) {
        var f = App.NewForm(App.T("pick_title"), 1280, 920); Text = f.Text; BackColor = f.BackColor; ForeColor = f.ForeColor; Font = f.Font; Icon = f.Icon; App.Front(this);
        Size = f.Size; StartPosition = FormStartPosition.Manual; Location = f.Location;
        var flow = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoScroll = true, Padding = new Padding(10), BackColor = App.Bg };
        bool en = App.Lang == "en";
        foreach (var o in outfits) {
            var card = new Panel { Size = new Size(214, 480), Margin = new Padding(7), BackColor = App.Card, Cursor = Cursors.Hand };
            var pic = new PictureBox { Location = new Point(7, 7), Size = new Size(200, 300), SizeMode = PictureBoxSizeMode.Zoom, BackColor = Color.FromArgb(28, 30, 36) };
            pic.Image = App.LoadImage(Path.Combine(App.Root, @"data\previews\" + o.id + ".jpg"));
            if (pic.Image == null) pic.Controls.Add(new Label { Text = App.T("nopreview"), ForeColor = App.Sub, Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleCenter });
            var cb = new CheckBox { Location = new Point(10, 312), Size = new Size(198, 46), Text = en ? o.eve_en : o.eve_ko, Tag = o.id, Font = App.F(10, true), ForeColor = App.Fg, FlatStyle = FlatStyle.Flat };
            var armor = en ? o.armor_en : o.armor_ko; var note = en ? o.note_en : o.note_ko;
            var info = new Label { Location = new Point(10, 360), Size = new Size(198, 116), ForeColor = App.Sub,
                Text = App.T("pick_eve") + ": " + (en ? o.eve_en : o.eve_ko) + " (" + (en ? o.eve_ko : o.eve_en) + ")\n" +
                       App.T("pick_armor") + ": " + armor + (string.IsNullOrEmpty(note) ? "" : "  (" + note + ")") + "\n" +
                       (en ? o.where_en : o.where_ko) + (string.IsNullOrEmpty(o.dlc) ? "" : "\n" + o.dlc + " DLC - " + App.T("pick_dlc")) };
            if (!string.IsNullOrEmpty(o.dlc)) info.ForeColor = App.Dlc;
            EventHandler toggle = delegate { cb.Checked = !cb.Checked; };
            pic.Click += toggle; info.Click += toggle; card.Click += toggle;
            cb.CheckedChanged += delegate { card.BackColor = cb.Checked ? App.CardOn : App.Card; UpdateCount(); };
            card.Controls.Add(pic); card.Controls.Add(cb); card.Controls.Add(info); flow.Controls.Add(card); boxes.Add(cb);
        }
        var bar = new Panel { Dock = DockStyle.Bottom, Height = 62, BackColor = App.Panel };
        var left = new FlowLayoutPanel { Dock = DockStyle.Left, Width = 520, Padding = new Padding(14, 16, 0, 0), WrapContents = false };
        left.Controls.Add(new Label { Text = App.T("pick_jobs"), AutoSize = true, ForeColor = App.Sub, Margin = new Padding(0, 7, 6, 0) });
        var jobs = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 46, BackColor = App.Card, ForeColor = App.Fg, FlatStyle = FlatStyle.Flat };
        for (int i = 1; i <= 4; i++) jobs.Items.Add(i.ToString()); jobs.SelectedItem = defJobs.ToString();
        var sc = new CheckBox { Text = App.T("pick_shortcut"), AutoSize = true, Checked = true, ForeColor = App.Fg, FlatStyle = FlatStyle.Flat, Margin = new Padding(18, 5, 0, 0) };
        left.Controls.Add(jobs); left.Controls.Add(sc);
        var right = new FlowLayoutPanel { Dock = DockStyle.Right, Width = 700, FlowDirection = FlowDirection.RightToLeft, Padding = new Padding(0, 13, 14, 0), WrapContents = false };
        var install = App.Btn(App.T("pick_install"), 130, true); var back = App.Btn(App.T("pick_back"), 100);
        var all = App.Btn(App.T("pick_all"), 120); var clear = App.Btn(App.T("pick_clear"), 120);
        count = new Label { AutoSize = true, ForeColor = App.Accent, Font = App.F(10, true), Margin = new Padding(12, 8, 8, 0) };
        right.Controls.Add(install); right.Controls.Add(back); right.Controls.Add(clear); right.Controls.Add(all); right.Controls.Add(count);
        bar.Controls.Add(left); bar.Controls.Add(right);
        install.Click += delegate {
            Selected = boxes.Where(b => b.Checked).Select(b => (string)b.Tag).ToList();
            if (Selected.Count == 0) { MessageBox.Show(this, App.T("pick_none"), "Stellar Eve"); return; }
            if (App.GameRunning()) { MessageBox.Show(this, App.T("game_running"), "Stellar Eve"); return; }
            Jobs = int.Parse((string)jobs.SelectedItem); Shortcut = sc.Checked; ok = true; Close();
        };
        back.Click += delegate { Close(); };
        all.Click += delegate { foreach (var b in boxes) b.Checked = true; };
        clear.Click += delegate { foreach (var b in boxes) b.Checked = false; };
        Controls.Add(flow); Controls.Add(App.Header(App.T("pick_sub"))); Controls.Add(bar);
        UpdateCount();
    }
    Label count;
    void UpdateCount() { if (count != null) count.Text = string.Format(App.T("pick_count"), boxes.Count(b => b.Checked)); }
    public bool Run() { ShowDialog(); return ok; }
}

class Plan { public bool tools, prepare; public int bases, outfits, jobs; }

class ProgressForm : Form {
    readonly Label pct, step, detail; readonly Panel track, fill; readonly TextBox log; readonly Button cancel, close, openLog;
    readonly System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer { Interval = 400 };
    readonly Queue<string> lines = new Queue<string>(); readonly object gate = new object();
    readonly Process proc; readonly Plan plan; readonly bool uninstall; readonly DateTime started = DateTime.Now; readonly string logFile;
    int tools, bases, outs; bool prep, inst, done, cancelled, finished; string phase = "tools", lastErr = ""; DateTime phaseAt = DateTime.Now;

    public ProgressForm(string title, string sub, string args, Plan plan, bool uninstall) {
        this.plan = plan; this.uninstall = uninstall;
        var f = App.NewForm(title, 780, 620); Text = f.Text; BackColor = f.BackColor; ForeColor = f.ForeColor; Font = f.Font; Icon = f.Icon; App.Front(this);
        Size = f.Size; StartPosition = FormStartPosition.Manual; Location = f.Location; FormBorderStyle = FormBorderStyle.FixedSingle; MaximizeBox = false;
        var body = new Panel { Dock = DockStyle.Fill };
        pct = new Label { Text = uninstall ? "" : "0%", Font = App.F(34, true), ForeColor = App.Accent, AutoSize = true, Location = new Point(24, 10) };
        step = new Label { Text = uninstall ? App.T("un_running") : App.T("st_start"), Font = App.F(11, true), AutoSize = true, Location = new Point(28, 80) };
        track = new Panel { BackColor = App.Track, Location = new Point(28, 112), Size = new Size(ClientSize.Width - 56, 14) };
        fill = new Panel { BackColor = App.Accent, Location = new Point(0, 0), Size = new Size(0, 14) }; track.Controls.Add(fill);
        detail = new Label { ForeColor = App.Sub, AutoSize = true, Location = new Point(28, 134), MaximumSize = new Size(ClientSize.Width - 56, 40) };
        log = new TextBox { Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical, BackColor = Color.FromArgb(14, 15, 18), ForeColor = App.Sub,
            Font = new Font("Consolas", 8.5f), BorderStyle = BorderStyle.None, Location = new Point(28, 172), Size = new Size(ClientSize.Width - 56, ClientSize.Height - 104 - 172 - 74) };
        body.Controls.Add(pct); body.Controls.Add(step); body.Controls.Add(track); body.Controls.Add(detail); body.Controls.Add(log);
        var bar = new FlowLayoutPanel { Dock = DockStyle.Bottom, Height = 58, BackColor = App.Panel, FlowDirection = FlowDirection.RightToLeft, Padding = new Padding(0, 11, 14, 0) };
        close = App.Btn(App.T("btn_close"), 120, true); close.Visible = false; cancel = App.Btn(App.T("btn_cancel"), 120); openLog = App.Btn(App.T("btn_log"), 140);
        bar.Controls.Add(close); bar.Controls.Add(cancel); bar.Controls.Add(openLog);
        Controls.Add(body); Controls.Add(App.Header(sub)); Controls.Add(bar);

        logFile = Path.Combine(App.Root, "install_log.txt"); File.WriteAllText(logFile, "", Encoding.UTF8);
        var psi = new ProcessStartInfo("powershell.exe", "-NoProfile -ExecutionPolicy Bypass -File \"" + Path.Combine(App.Root, "install.ps1") + "\" -NoGui -Yes " + args) {
            WorkingDirectory = App.Root, UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true, RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8 };
        proc = new Process { StartInfo = psi, EnableRaisingEvents = true };
        DataReceivedEventHandler h = (s, e) => { if (e.Data != null) lock (gate) lines.Enqueue(e.Data); };
        proc.OutputDataReceived += h; proc.ErrorDataReceived += h;
        proc.Start(); proc.BeginOutputReadLine(); proc.BeginErrorReadLine();
        timer.Tick += delegate { Tick(); }; timer.Start();
        cancel.Click += delegate { AskStop(); };
        close.Click += delegate { Close(); };
        openLog.Click += delegate { try { Process.Start("notepad.exe", "\"" + logFile + "\""); } catch { } };
        FormClosing += (s, e) => { if (!finished) { if (!AskStop()) e.Cancel = true; } };
    }
    bool AskStop() {
        if (MessageBox.Show(this, App.T("ask_stop"), "Stellar Eve", MessageBoxButtons.YesNo) != DialogResult.Yes) return false;
        cancelled = true;
        try { Process.Start(new ProcessStartInfo("taskkill.exe", "/PID " + proc.Id + " /T /F") { CreateNoWindow = true, UseShellExecute = false }); } catch { }
        return true;
    }
    static readonly Regex OutfitDone = new Regex(@"=== (outfit \d+ (finished|\(.*skipped)|make_eve_auto\.py \d+ finished)");
    void Tick() {
        var batch = new List<string>();
        lock (gate) while (lines.Count > 0) batch.Add(lines.Dequeue());
        if (batch.Count > 0) {
            var sb = new StringBuilder();
            foreach (var l in batch) {
                if (string.IsNullOrWhiteSpace(l) || Regex.IsMatch(l, @"^\s*[\d%]")) continue;   // curl progress lines
                sb.AppendLine(l); Parse(l);
            }
            if (sb.Length > 0) { log.AppendText(sb.ToString()); try { File.AppendAllText(logFile, sb.ToString(), Encoding.UTF8); } catch { } }
        }
        var el = DateTime.Now - started; var els = string.Format("{0:00}:{1:00}", (int)el.TotalMinutes, el.Seconds);
        if (!uninstall) {
            int p = Percent();
            pct.Text = p + "%"; fill.Width = track.Width * p / 100;
            step.Text = phase == "tools" ? string.Format(App.T("st_tools"), Math.Min(tools, 9)) : phase == "prep" ? App.T("st_prep") : phase == "base" ? App.T("st_base")
                      : phase == "outfits" ? string.Format(App.T("st_outfits"), Math.Min(outs, plan.outfits), plan.outfits) : App.T("st_inst");
            detail.Text = string.Format(App.T("detail"), els, plan.outfits, plan.jobs);
        } else {
            fill.Width = (int)(track.Width * (0.5 + 0.45 * (1 - Math.Exp(-el.TotalSeconds / 10))));
        }
        if (proc.HasExited && !finished) Finish(els);
    }
    void Parse(string l) {
        if (l.Contains("[stellar-eve] downloading")) { tools++; Phase("tools"); }
        else if (l.Contains("Build succeeded") || l.Contains("빌드했습니다")) tools++;   // dotnet prints it in the Windows language
        else if (Regex.IsMatch(l, @"=== prepare\.py\s*$")) Phase("prep");
        else if (l.Contains("=== prepare.py finished")) { prep = true; tools = 9; Phase("base"); }
        else if (Regex.IsMatch(l, @"\[build_base\] (27|63) done")) { bases++; phaseAt = DateTime.Now; }
        else if (l.Contains("=== build_base.py finished") || l.Contains("default looks already built")) { if (plan != null) bases = plan.bases; Phase("outfits"); }
        else if (OutfitDone.IsMatch(l)) { outs++; Phase("outfits"); }
        else if (l.Contains("failed outfits:")) { if (plan != null) outs = plan.outfits; Phase("inst"); }
        else if (Regex.IsMatch(l, @"^installed \d+ files")) inst = true;
        else if (Regex.IsMatch(l, @"\[stellar-eve\] (done|built \(not installed\))") || l.StartsWith("removed ")) done = true;
        if (Regex.IsMatch(l, "Exception|Error|error|failed|not found|is running|nothing")) lastErr = l;
    }
    void Phase(string p) { phase = p; phaseAt = DateTime.Now; }
    int Percent() {
        // weighted steps: tool downloads, game extraction, face / default looks, outfits, install
        double wT = plan.tools ? 18 : 0, wP = plan.prepare ? 6 : 1, wB = 7.0 * plan.bases, wO = plan.outfits > 0 ? 62 : 0, wI = 3, total = wT + wP + wB + wO + wI;
        double d = Math.Min(tools, 9) / 9.0 * wT + (prep ? wP : 0) + Math.Min(bases, plan.bases) * 7.0 + (plan.outfits > 0 ? Math.Min(outs, plan.outfits) / (double)plan.outfits * wO : 0) + (inst ? wI : 0);
        // slow creep inside the current step so the bar keeps moving between log lines
        double unit = phase == "tools" ? wT / 9 : phase == "prep" ? wP : phase == "base" ? 7 : phase == "outfits" ? (plan.outfits > 0 ? wO / plan.outfits * Math.Max(1, plan.jobs) : 0) : wI;
        double guess = phase == "tools" ? 25 : phase == "prep" ? 90 : phase == "base" ? 110 : phase == "outfits" ? 150 : 15;
        if (!done) d += unit * 0.9 * (1 - Math.Exp(-(DateTime.Now - phaseAt).TotalSeconds / guess));
        return done ? 100 : Math.Min(99, (int)(d / total * 100));
    }
    void Finish(string els) {
        finished = true; timer.Stop(); proc.WaitForExit();
        Tick();   // last lines
        finished = true; cancel.Visible = false; close.Visible = true;
        if (cancelled) { step.Text = App.T("st_cancel"); step.ForeColor = App.Sub; return; }
        if (proc.ExitCode == 0 && done) {
            pct.Text = uninstall ? "" : "100%"; fill.Width = track.Width;
            step.Text = uninstall ? App.T("un_done") : App.T("st_done");
            detail.Text = uninstall ? string.Format(App.T("un_done_d"), App.Root) : string.Format(App.T("took"), els);
        } else {
            step.Text = App.T("st_fail"); step.ForeColor = App.Bad; pct.ForeColor = App.Bad; fill.BackColor = App.Bad;
            detail.Text = string.IsNullOrEmpty(lastErr) ? "exit code " + proc.ExitCode : lastErr; detail.ForeColor = App.Bad;
        }
    }
}
