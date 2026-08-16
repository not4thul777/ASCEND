import cv2
import winsound
import customtkinter as ctk
from tkinter import messagebox
from datetime import timedelta
from pathlib import Path
from PIL import Image, ImageTk
from database import (
    get_profile, set_name, add_log, today_logs, category_totals_24h,
    stat_totals, quests_today, complete_quest, quest_time_left, quest_progress,
    gym_history, gym_summary, get_equipped_badge, equip_badge,
    badge_unlocked
)

BG="#050914"; PANEL="#091726"; PANEL2="#0D2233"
ACCENT="#16A8FF"; CYAN="#65E5FF"; TEXT="#F7FCFF"
MUTED="#7893A7"; GREEN="#4ADE80"; DANGER="#FF5577"
FPS=16
SOUND_DIR = Path(__file__).parent / "assets" / "sounds"


def play_sound(filename):
    path = SOUND_DIR / filename
    if not path.exists():
        return
    try:
        winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
    except Exception:
        pass


def bind_hover(widget):
    widget.bind("<Enter>", lambda event: play_sound("hover.wav"), add="+")
    return widget

class BackgroundManager:
    def __init__(self, app, parent):
        self.app=app
        self.parent=parent
        self.label=ctk.CTkLabel(parent,text="",fg_color=BG)
        self.label.place(relx=0,rely=0,relwidth=1,relheight=1)
        self.label.lower()
        self.images={}
        self.base=Path(__file__).parent/"assets"
        self.load("system",self.base/"system_blue.jpg")
        self.load("persona",self.base/"persona_black.jpg")
        self.load("crystal",self.base/"crystal_blue.jpg")
        self.set("system")

    def load(self,key,path):
        if path.exists():
            img=Image.open(path).convert("RGB")
            self.images[key]=ctk.CTkImage(light_image=img,dark_image=img,size=(1100,740))

    def set(self,key):
        if key not in self.images:
            key="system"
        self.label.configure(image=self.images[key],text="")
        self.label.lower()

    def add_hud_overlay(self, page):
        # Subtle scanline/frame accents that remain behind page content.
        for w in getattr(self, "_hud", []):
            try:
                w.destroy()
            except Exception:
                pass
        self._hud = []

        line1 = ctk.CTkFrame(
            self.parent, fg_color="#0EA5E9", height=1,
            corner_radius=0
        )
        line1.place(relx=0.035, rely=0.055, relwidth=0.93)
        line1.lower(self.label)

        line2 = ctk.CTkFrame(
            self.parent, fg_color="#12344B", height=1,
            corner_radius=0
        )
        line2.place(relx=0.035, rely=0.935, relwidth=0.93)
        line2.lower(self.label)

        tag = ctk.CTkLabel(
            self.parent,
            text=f"// SYSTEM :: {page.upper()}",
            text_color="#4CCFFF",
            fg_color="#06101A",
            font=ctk.CTkFont(size=8, weight="bold")
        )
        tag.place(relx=0.045, rely=0.042)
        tag.lower(self.label)

        right_tag = ctk.CTkLabel(
            self.parent,
            text="ONLINE  //  60 FPS",
            text_color="#4CCFFF",
            fg_color="#06101A",
            font=ctk.CTkFont(size=8, weight="bold")
        )
        right_tag.place(relx=0.82, rely=0.042)
        right_tag.lower(self.label)

        self._hud.extend([line1, line2, tag, right_tag])

class CircularMeter(ctk.CTkCanvas):
    def __init__(self, master, size=260, thickness=14):
        super().__init__(master,width=size,height=size,bg=BG,highlightthickness=0)
        self.size=size; pad=thickness+8
        self.arc=self.create_arc(pad,pad,size-pad,size-pad,start=90,extent=0,
                                 style="arc",outline=ACCENT,width=thickness)
        self.create_oval(pad+thickness,pad+thickness,size-pad-thickness,size-pad-thickness,
                         fill=PANEL,outline="")
        self.value_text=self.create_text(size/2,size/2-8,text="0%",fill=TEXT,
                                         font=("Segoe UI",28,"bold"))
        self.create_text(size/2,size/2+27,text="LEVEL PROGRESS",fill=MUTED,
                         font=("Segoe UI",9,"bold"))
    def set_progress(self,value):
        value=max(0,min(1,value))
        self.itemconfigure(self.arc,extent=-360*value)
        self.itemconfigure(self.value_text,text=f"{int(value*100)}%")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.camera = None
        self.camera_running = False
        self.face_cascade = None

        # Look for the Haar cascade locally first, then in OpenCV's data folder.
        cascade_candidates = [
            Path(__file__).parent / "assets" / "haarcascade_frontalface_default.xml"
        ]
        try:
            cascade_candidates.append(
                Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
            )
        except Exception:
            pass

        for cascade_path in cascade_candidates:
            if cascade_path.exists():
                detector = cv2.CascadeClassifier(str(cascade_path))
                if not detector.empty():
                    self.face_cascade = detector
                    break

        self.title("ASCEND // SYSTEM ONLINE")
        self.geometry("1200x740"); self.minsize(1050,680)
        self.configure(fg_color=BG); self.closing=False
        try:
            self.attributes("-alpha",0.0); self.alpha_supported=True
        except Exception:
            self.alpha_supported=False
        self.protocol("WM_DELETE_WINDOW",self.fade_out)
        self.build_sidebar()
        self.content=ctk.CTkFrame(self,fg_color=BG,corner_radius=0)
        self.content.pack(side="left",fill="both",expand=True)

        # Dedicated background host. It survives page changes.
        self.background_host=ctk.CTkFrame(
            self.content, fg_color=BG, corner_radius=0
        )
        self.background_host.place(relx=0,rely=0,relwidth=1,relheight=1)
        self.backgrounds=BackgroundManager(self,self.background_host)

        # Page content sits above the background.
        self.page_host=ctk.CTkFrame(
            self.content, fg_color="transparent", corner_radius=0
        )
        self.page_host.place(relx=0,rely=0,relwidth=1,relheight=1)
        self.show_page("dashboard")
        self.after(FPS,lambda:self.fade_in(0))

    def fade_in(self,a):
        if not self.alpha_supported:return
        a=min(1,a+.055); self.attributes("-alpha",a)
        if a<1:self.after(FPS,lambda:self.fade_in(a))

    def fade_out(self):
        if self.closing:return
        self.closing=True; self.fade_out_step(1)

    def fade_out_step(self,a):
        if not self.alpha_supported:self.destroy();return
        a-=.055
        if a<=0:self.attributes("-alpha",0);self.destroy();return
        self.attributes("-alpha",a);self.after(FPS,lambda:self.fade_out_step(a))

    def load_profile_image(self):
        """Use the player's equipped rank badge as the profile picture."""
        badge = get_equipped_badge()

        # Default to the current rank badge if nothing has been equipped yet.
        if not badge:
            profile = get_profile()
            badge = profile["rank"]

        path = (
            Path(__file__).parent
            / "assets"
            / "badges"
            / f"{badge.lower().replace('-', '_')}.png"
        )

        try:
            if path.exists():
                img = Image.open(path).convert("RGBA")
                return ctk.CTkImage(
                    light_image=img,
                    dark_image=img,
                    size=(82, 82)
                )
        except Exception:
            pass

        return None

    def build_sidebar(self):
        side = ctk.CTkFrame(
            self,
            width=215,
            fg_color="#06101B",
            corner_radius=0,
            border_width=1,
            border_color="#12354A"
        )
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        ctk.CTkLabel(
            side,
            text="A S C E N D",
            text_color=CYAN,
            font=ctk.CTkFont(size=23, weight="bold")
        ).pack(pady=(30,2))

        ctk.CTkLabel(
            side,
            text="PERSONAL PROGRESSION SYSTEM",
            text_color=MUTED,
            font=ctk.CTkFont(size=9)
        ).pack(pady=(0,10))

        profile_row = ctk.CTkFrame(side, fg_color="transparent")
        profile_row.pack(fill="x", padx=12, pady=(0,14))

        pfp_frame = ctk.CTkFrame(
            profile_row,
            width=94,
            height=94,
            fg_color="#071521",
            border_width=1,
            border_color="#1C8EBB",
            corner_radius=47
        )
        pfp_frame.pack(side="left", padx=(0,9))
        pfp_frame.pack_propagate(False)

        self.profile_image = self.load_profile_image()
        self.pfp_label = ctk.CTkLabel(
            pfp_frame,
            text="P",
            image=self.profile_image,
            text_color=CYAN,
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.pfp_label.place(relx=0.5, rely=0.5, anchor="center")

        p = get_profile()
        identity = ctk.CTkFrame(profile_row, fg_color="transparent")
        identity.pack(side="left", fill="x", expand=True)

        self.sidebar_name = ctk.CTkLabel(
            identity,
            text=p["name"],
            text_color=TEXT,
            font=ctk.CTkFont(size=15, weight="bold"),
            wraplength=85,
            anchor="w",
            justify="left"
        )
        self.sidebar_name.pack(anchor="w")

        self.sidebar_rank = ctk.CTkLabel(
            identity,
            text=p["rank"],
            text_color=CYAN,
            font=ctk.CTkFont(size=9, weight="bold")
        )
        self.sidebar_rank.pack(anchor="w", pady=(2,0))

        ctk.CTkLabel(
            identity,
            text="EQUIPPED RANK BADGE",
            text_color="#6B9DB3",
            font=ctk.CTkFont(size=8, weight="bold")
        ).pack(anchor="w", pady=(3,0))

        self.nav = {}

        for text, key in [
            ("⌂  DASHBOARD", "dashboard"),
            ("⚔  LOG ACTIVITY", "log"),
            ("▣  DAILY QUESTS", "quests"),
            ("◈  STATUS", "status"),
            ("◉  SYSTEM SCAN", "scan"),
            ("◷  GYM HISTORY", "history"),
            ("◫  STUDY HISTORY", "study_history"),
            ("♙  SOCIAL HISTORY", "social_history"),
            ("♜  ARENA", "arena"),
            ("◉  PROFILE", "profile"),
        ]:
            b = ctk.CTkButton(
                side,
                text=text,
                anchor="w",
                height=41,
                fg_color="transparent",
                hover_color=PANEL2,
                text_color=TEXT,
                command=lambda k=key: (
                    play_sound("click.wav"),
                    self.show_page(k)
                )
            )
            b.pack(fill="x", padx=14, pady=3)
            bind_hover(b)
            self.nav[key] = b

        ctk.CTkFrame(side, fg_color="transparent").pack(
            expand=True, fill="both"
        )

        quit_button = ctk.CTkButton(
            side,
            text="✕  QUIT SYSTEM",
            anchor="w",
            height=42,
            fg_color="transparent",
            hover_color="#331722",
            text_color=DANGER,
            command=self.fade_out
        )
        quit_button.pack(fill="x", padx=14, pady=(0,8))
        bind_hover(quit_button)

        ctk.CTkLabel(
            side,
            text="● SYSTEM ONLINE",
            text_color=GREEN,
            font=ctk.CTkFont(size=10, weight="bold")
        ).pack(pady=(0,25))

    def update_badge_avatar(self):
        """Refresh the equipped rank badge used as the sidebar PFP."""
        if not hasattr(self, "pfp_label"):
            return
        self.profile_image = self.load_profile_image()
        self.pfp_label.configure(
            image=self.profile_image,
            text="" if self.profile_image else "?"
        )

    def show_page(self,page):
        if page != "scan":
            self.stop_camera()
        self.clear()
        if hasattr(self, "pfp_label"):
            self.update_badge_avatar()

        # The equipped rank badge is also the player's sidebar PFP.
        if hasattr(self, "profile_image") and hasattr(self, "pfp_label"):
            self.profile_image = self.load_profile_image()
            self.pfp_label.configure(
                image=self.profile_image,
                text="" if self.profile_image else "?"
            )

        if hasattr(self, "sidebar_name"):
            p = get_profile()
            self.sidebar_name.configure(text=p["name"])
            self.sidebar_rank.configure(text=p["rank"])
        for k,b in self.nav.items():
            active = (k == page)
            b.configure(
                fg_color=PANEL2 if active else "transparent",
                border_width=1 if active else 0
            )
            # CustomTkinter does not allow transparent border_color.
            # Only set a real color when the button is active.
            if active:
                b.configure(border_color="#1CB7FF")
            else:
                b.configure(border_color="#06101A")
        bg_map={
            "dashboard":"system","log":"crystal","quests":"crystal",
            "status":"persona","arena":"persona","history":"system",
            "study_history":"persona","social_history":"system","profile":"persona"
        }
        if hasattr(self,"backgrounds"):
            self.backgrounds.set(bg_map.get(page,"system"))
            self.backgrounds.add_hud_overlay(page)
        fn={"dashboard":self.dashboard,"log":self.log_activity,"quests":self.quests,
            "status":self.status,"arena":self.arena,"history":self.history,
            "study_history":self.study_history,"social_history":self.social_history,"profile":self.profile,"scan": self.system_scan,}[page]
        fn()

    def clear(self):
        # Keep one persistent cinematic background behind every page.
        for w in self.page_host.winfo_children():
            w.destroy()

    def header(self,title,sub):
        band=ctk.CTkFrame(
            self.page_host,
            fg_color="#06101A",
            border_width=1,
            border_color="#1E8DBB",
            corner_radius=2,
            height=78
        )
        band.pack(fill="x",padx=30,pady=(22,14))
        band.pack_propagate(False)

        accent=ctk.CTkFrame(band,fg_color="#19BFFF",width=4,corner_radius=0)
        accent.pack(side="left",fill="y")

        lab=ctk.CTkLabel(
            band,text="",text_color=TEXT,
            font=ctk.CTkFont(size=25,weight="bold")
        )
        lab.pack(anchor="w",padx=20,pady=(10,0))
        ctk.CTkLabel(
            band,text=sub,text_color="#70A8C0",
            font=ctk.CTkFont(size=10,weight="bold")
        ).pack(anchor="w",padx=20,pady=(1,5))
        self.type_text(lab,title,0)

    def type_text(self,lab,text,i):
        if not lab.winfo_exists():return
        lab.configure(text=text[:i])
        if i<len(text):self.after(FPS,lambda:self.type_text(lab,text,i+1))

    def progress(self,bar,target,v=0):
        v=min(target,v+.035);bar.set(v)
        if v<target and bar.winfo_exists():self.after(FPS,lambda:self.progress(bar,target,v))

    def meter(self,m,target,v=0):
        v=min(target,v+.03);m.set_progress(v)
        if v<target and m.winfo_exists():self.after(FPS,lambda:self.meter(m,target,v))

    def holo_panel(self, parent, width=0, height=0):
        return ctk.CTkFrame(
            parent,
            fg_color="#071521",
            border_width=1,
            border_color="#1B526A",
            corner_radius=3,
            width=width,
            height=height
        )

    def circular_stat(self, parent, code, name, value, max_value=100, size=120):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        canvas = ctk.CTkCanvas(
            wrap, width=size, height=size,
            bg="#071521", highlightthickness=0
        )
        canvas.pack()
        pad=10
        canvas.create_oval(
            pad,pad,size-pad,size-pad,
            outline="#17364A",width=8
        )
        ratio=max(0,min(1,value/max_value))
        canvas.create_arc(
            pad,pad,size-pad,size-pad,
            start=90,extent=-360*ratio,
            style="arc",outline="#1FC3FF",width=8
        )
        canvas.create_text(
            size/2,size/2-7,text=str(int(value)),
            fill=TEXT,font=("Segoe UI",20,"bold")
        )
        canvas.create_text(
            size/2,size/2+20,text=code,
            fill="#6DBBDB",font=("Segoe UI",8,"bold")
        )
        ctk.CTkLabel(
            wrap,text=name,text_color="#D8EFF9",
            font=ctk.CTkFont(size=9,weight="bold")
        ).pack(pady=(2,0))
        return wrap

    def rank_requirements(self):
        return [
            ("E-RANK", 0),
            ("D-RANK", 1500),
            ("C-RANK", 4000),
            ("B-RANK", 8000),
            ("A-RANK", 14000),
            ("S-RANK", 22000),
            ("NATIONAL", 35000),
        ]

    def dashboard(self):
        self.header("SYSTEM DASHBOARD","Your real-world progression, quantified.")
        p=get_profile(); t=category_totals_24h()
        wrap=ctk.CTkFrame(self.page_host,fg_color="transparent");wrap.pack(fill="both",expand=True,padx=35)
        left=ctk.CTkFrame(wrap,fg_color=PANEL,corner_radius=4,border_width=1,border_color="#164A63")
        left.pack(side="left",fill="both",expand=True,padx=(0,8))
        ctk.CTkLabel(left,text=f"PLAYER // {p['name'].upper()}",text_color="#72BDD8",
                     font=ctk.CTkFont(size=10,weight="bold")).pack(pady=(18,0))
        ctk.CTkLabel(left,text=p["rank"],text_color=CYAN,font=ctk.CTkFont(size=34,weight="bold")).pack()
        m=CircularMeter(left,250);m.pack(pady=5)
        current=p["xp"]; level=1
        while current >= 250 + (level - 1) * 100:
            current -= 250 + (level - 1) * 100
            level += 1
        req = 250 + (level - 1) * 100
        self.after(FPS,lambda:self.meter(m,current/req))
        ctk.CTkLabel(left,text=f"LEVEL {p['level']}  •  {p['xp']} TOTAL XP",
                     text_color=TEXT,font=ctk.CTkFont(size=13,weight="bold")).pack()
        next_ranks = [
            ("D-RANK", 1500), ("C-RANK", 4000), ("B-RANK", 8000),
            ("A-RANK", 14000), ("S-RANK", 22000), ("NATIONAL", 35000)
        ]
        nxt = next(((name, req) for name, req in next_ranks if p["xp"] < req), None)
        if nxt:
            ctk.CTkLabel(
                left,
                text=f"NEXT RANK  {nxt[0]}  •  {nxt[1] - p['xp']} XP TO GO",
                text_color="#72BDD8",
                font=ctk.CTkFont(size=9,weight="bold")
            ).pack(pady=(3,0))
        next_rank = next(((name, xp) for name, xp in self.rank_requirements()
                          if xp > p["xp"]), None)
        if next_rank:
            needed = next_rank[1] - p["xp"]
            ctk.CTkLabel(
                left,
                text=f"NEXT RANK  {next_rank[0]}  •  {needed} XP TO GO",
                text_color="#72BDD8",
                font=ctk.CTkFont(size=9,weight="bold")
            ).pack(pady=(4,0))
        else:
            ctk.CTkLabel(
                left,text="MAXIMUM RANK REACHED",
                text_color="#72BDD8",
                font=ctk.CTkFont(size=9,weight="bold")
            ).pack(pady=(4,0))
        ctk.CTkLabel(left,text=f"ARENA POWER  {p['arena_points']} AP",text_color=ACCENT,
                     font=ctk.CTkFont(size=12,weight="bold")).pack(pady=(8,6))
        ctk.CTkButton(
            left,text="EDIT PROFILE",width=135,height=30,
            fg_color="#0C2B3B",hover_color="#124A62",
            border_width=1,border_color="#1C8EBB",
            command=self.name_dialog
        ).pack(pady=(0,16))

        right=ctk.CTkFrame(wrap,fg_color="transparent");right.pack(side="left",fill="both",expand=True,padx=(8,0))
        pulse=ctk.CTkFrame(right,fg_color=PANEL,corner_radius=4,border_width=1,border_color="#164A63");pulse.pack(fill="x",pady=(0,8))
        ctk.CTkLabel(pulse,text="LAST 24 HOURS",text_color=MUTED).pack(anchor="w",padx=20,pady=(18,8))
        for key,unit in [("Gym","sessions"),("Study","hrs"),("Social","people")]:
            v=t.get(key,0) or 0
            ctk.CTkLabel(pulse,text=f"{key.upper():<9} {v:g} {unit}",text_color=TEXT,
                         font=ctk.CTkFont(family="Consolas",size=12)).pack(anchor="w",padx=20,pady=3)
        quick=ctk.CTkFrame(right,fg_color=PANEL,corner_radius=4,border_width=1,border_color="#164A63");quick.pack(fill="both",expand=True)
        ctk.CTkLabel(quick,text="RECENT ACTIVITY",text_color=TEXT,
                     font=ctk.CTkFont(size=15,weight="bold")).pack(anchor="w",padx=20,pady=(18,10))
        logs=today_logs()
        if not logs:ctk.CTkLabel(quick,text="No activity logged yet.",text_color=MUTED).pack(padx=20,anchor="w")
        for i,l in enumerate(logs[:7]):self.after(FPS*i,lambda x=l:self.add_log_row(quick,x))

    def add_log_row(self,parent,l):
        r=ctk.CTkFrame(parent,fg_color=PANEL2,corner_radius=2);r.pack(fill="x",padx=15,pady=3)
        ctk.CTkLabel(r,text=l["category"].upper(),width=80,text_color=CYAN).pack(side="left",padx=10,pady=8)
        ctk.CTkLabel(r,text=f"{l['item']} • {l['value']:g} {l['unit']}",text_color=TEXT).pack(side="left")
        ctk.CTkLabel(r,text=f"+{l['xp']} XP",text_color=GREEN).pack(side="right",padx=10)

    def log_activity(self):
        self.header("LOG ACTIVITY","Every real action becomes progression.")
        box=ctk.CTkFrame(self.page_host,fg_color="transparent");box.pack(fill="both",expand=True,padx=35)
        cards=[("GYM","Exercise, weight, reps & sets",self.gym_form),
               ("STUDY","Focused study time",lambda:self.simple_form("Study","Study session","hours","INT",6,24)),
               ("SOCIAL","People you talked to",lambda:self.simple_form("Social","People talked to","people","SOC",3,100))]
        for i,(title,desc,cmd) in enumerate(cards):
            f=ctk.CTkFrame(box,fg_color=PANEL,corner_radius=4);f.grid(row=0,column=i,sticky="nsew",padx=7)
            box.grid_columnconfigure(i,weight=1);box.grid_rowconfigure(0,weight=1)
            ctk.CTkLabel(f,text=title,text_color=CYAN,font=ctk.CTkFont(size=22,weight="bold")).pack(pady=(50,6))
            ctk.CTkLabel(f,text=desc,text_color=MUTED,wraplength=190).pack(pady=5)
            action_button=ctk.CTkButton(
                f,text="OPEN LOGGER  →",fg_color=ACCENT,
                hover_color="#6246DC",
                command=lambda fn=cmd:(play_sound("click.wav"), fn())
            )
            action_button.pack(pady=30)
            bind_hover(action_button)

    def make_overlay(self,w=400,h=280):
        overlay=ctk.CTkFrame(self,fg_color="#000000");overlay.place(relx=0,rely=0,relwidth=1,relheight=1)
        panel=ctk.CTkFrame(overlay,fg_color=PANEL,corner_radius=4,width=w,height=h)
        panel.place(relx=.5,rely=.5,anchor="center")
        return overlay,panel

    def simple_form(self,category,item,unit,stat,base,max_value):
        overlay,panel=self.make_overlay()
        ctk.CTkLabel(panel,text=category.upper(),text_color=CYAN,font=ctk.CTkFont(size=22,weight="bold")).pack(pady=(28,8))
        ctk.CTkLabel(panel,text=f"Enter {unit}:",text_color=MUTED).pack()
        entry=ctk.CTkEntry(panel,placeholder_text="0");entry.pack(fill="x",padx=45,pady=10);entry.focus()
        def close():overlay.destroy()
        def save():
            try:
                v=float(entry.get())
                if v<=0 or v>max_value:raise ValueError
                xp=max(2,min(40,int(round(v*base))))
                event=add_log(category,item,v,unit,xp,stat)
                close()
                self.show_page("dashboard")
                if event.get("leveled_up") or event.get("ranked_up"):
                    play_sound("levelup.wav")
                if event.get("ranked_up"):
                    self.after(120, lambda r=event["rank"]: self.rankup_popup(r))
                self.after(70,lambda:self.xp_popup(xp))
            except ValueError:
                messagebox.showerror("Invalid Input",f"Enter a valid number between 0 and {max_value}.")
        ctk.CTkButton(panel,text="CONFIRM  +XP",fg_color=ACCENT,command=save).pack(pady=12)
        ctk.CTkButton(panel,text="CANCEL",fg_color="transparent",border_width=1,border_color=MUTED,
                      text_color=MUTED,command=close).pack()
        entry.bind("<Return>",lambda e:save());entry.bind("<Escape>",lambda e:close())

    def gym_form(self):
        overlay,panel=self.make_overlay(450,440)
        ctk.CTkLabel(panel,text="IRON DUNGEON",text_color=CYAN,font=ctk.CTkFont(size=23,weight="bold")).pack(pady=(24,2))
        ctk.CTkLabel(panel,text="Track your lift and build your history.",text_color=MUTED).pack(pady=(0,10))
        fields={}
        for label,ph in [("Exercise","Bench Press"),("Weight (kg)","20"),("Reps","8"),("Sets","3")]:
            ctk.CTkLabel(panel,text=label,text_color=MUTED).pack(anchor="w",padx=42,pady=(4,1))
            e=ctk.CTkEntry(panel,placeholder_text=ph);e.pack(fill="x",padx=42);fields[label]=e
        def save():
            try:
                ex=fields["Exercise"].get() or "Workout";w=float(fields["Weight (kg)"].get());r=int(fields["Reps"].get());s=int(fields["Sets"].get())
                if min(w,r,s)<=0:raise ValueError
                xp=max(5,min(60,int((w*r*s)/120)))
                event=add_log("Gym",ex,w,"kg",xp,"STR")
                overlay.destroy()
                self.show_page("history")
                if event.get("leveled_up") or event.get("ranked_up"):
                    play_sound("levelup.wav")
                if event.get("ranked_up"):
                    self.after(120, lambda r=event["rank"]: self.rankup_popup(r))
                self.after(70,lambda:self.xp_popup(xp))
            except ValueError:
                play_sound("error.wav")
                messagebox.showerror("Invalid Input","Check weight, reps and sets.")
        ctk.CTkButton(panel,text="COMPLETE SET  +XP",fg_color=ACCENT,command=save).pack(pady=15)
        ctk.CTkButton(panel,text="CANCEL",fg_color="transparent",border_width=1,border_color=MUTED,text_color=MUTED,command=overlay.destroy).pack()

    def xp_popup(self,xp):
        label=ctk.CTkLabel(self.page_host,text=f"+{xp} XP",text_color=GREEN,font=ctk.CTkFont(size=30,weight="bold"))
        label.place(relx=.62,rely=.48,anchor="center")
        def move(step=0):
            if not label.winfo_exists():return
            label.place_configure(rely=.48-step/1000)
            if step<100:self.after(FPS,lambda:move(step+4))
            else:label.destroy()
        move()

    def quests(self):
        # Always ask the database to validate/reset the current 24-hour cycle
        # before rendering the quest screen.
        from database import seed_quests
        seed_quests()
        self.header("DAILY QUESTS","Your quest cycle resets exactly every 24 hours.")
        left=quest_time_left();secs=max(0,int(left.total_seconds()))
        hrs,rem=divmod(secs,3600);mins,_=divmod(rem,60)
        ctk.CTkLabel(self.page_host,text=f"RESET IN  {hrs:02d}:{mins:02d}",text_color=CYAN,
                     font=ctk.CTkFont(size=13,weight="bold")).pack(anchor="e",padx=38,pady=(0,10))
        current_quests = quests_today()
        remaining_quests = sum(1 for q in current_quests if not q["done"])
        ctk.CTkLabel(
            self.page_host,
            text=f"AVAILABLE  {remaining_quests}/{len(current_quests)}",
            text_color="#59D8FF",
            font=ctk.CTkFont(size=10, weight="bold")
        ).pack(anchor="e", padx=38, pady=(0,6))
        for i,q in enumerate(current_quests):
            self.after(FPS*i,lambda x=q:self.quest_row(x))

    def quest_row(self,q):
        progress = quest_progress(q)
        target = float(q["target"])
        ratio = min(1.0, progress / target) if target else 0
        completed = progress >= target

        f=ctk.CTkFrame(
            self.page_host,
            fg_color="#071521",
            border_width=1,
            border_color="#1A526B" if not completed else "#21BFFF",
            corner_radius=3
        )
        f.pack(fill="x",padx=35,pady=6)

        l=ctk.CTkFrame(f,fg_color="transparent")
        l.pack(side="left",fill="x",expand=True,padx=18,pady=13)

        ctk.CTkLabel(
            l,text=q["title"],text_color=TEXT,
            font=ctk.CTkFont(size=15,weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            l,
            text=f"{q['target']:g} {q['unit']}  •  {q['stat']}  •  +{q['xp']} XP",
            text_color=MUTED
        ).pack(anchor="w",pady=(2,3))

        # Real progress bar.
        bar=ctk.CTkProgressBar(
            l,height=7,
            progress_color="#18BFFF" if completed else "#146080",
            fg_color="#0D2534"
        )
        bar.pack(fill="x",pady=(2,0))
        bar.set(ratio)

        ctk.CTkLabel(
            l,
            text=f"PROGRESS  {progress:g} / {target:g} {q['unit']}",
            text_color="#75C8E5",
            font=ctk.CTkFont(size=9,weight="bold")
        ).pack(anchor="w",pady=(3,0))

        if q["done"]:
            ctk.CTkLabel(
                f,text="✓ REWARD CLAIMED",
                text_color=GREEN,
                font=ctk.CTkFont(size=10,weight="bold")
            ).pack(side="right",padx=20)
        elif completed:
            ctk.CTkButton(
                f,text="CLAIM XP",
                width=120,
                fg_color=ACCENT,
                hover_color="#0878BB",
                command=lambda qid=q["id"]:(play_sound("click.wav"), self.claim(qid))
            ).pack(side="right",padx=20)
        else:
            ctk.CTkButton(
                f,text="IN PROGRESS",
                width=120,
                fg_color="#102532",
                hover_color="#102532",
                text_color="#6C92A5",
                state="disabled"
            ).pack(side="right",padx=20)

    def claim(self,qid):
        result = complete_quest(qid)
        if isinstance(result, tuple):
            xp, leveled_up = result
        else:
            xp, leveled_up = result, False

        self.show_page("quests")

        if xp:
            play_sound("success.wav")
            self.after(60, lambda: self.xp_popup(xp))

        if isinstance(leveled_up, dict):
            if leveled_up.get("leveled_up") or leveled_up.get("ranked_up"):
                self.after(90, lambda: play_sound("levelup.wav"))
            if leveled_up.get("ranked_up"):
                self.after(120, lambda r=leveled_up["rank"]: self.rankup_popup(r))
        elif leveled_up:
            self.after(90, lambda: play_sound("levelup.wav"))


    def rankup_popup(self, rank):
        popup = ctk.CTkFrame(
            self.page_host,
            fg_color="#06131F",
            border_width=2,
            border_color="#28C6FF",
            corner_radius=4
        )
        popup.place(relx=0.5, rely=0.28, anchor="center")

        ctk.CTkLabel(
            popup, text="RANK PROMOTION",
            text_color="#67DFFF",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(padx=34, pady=(14, 2))

        ctk.CTkLabel(
            popup, text=rank,
            text_color=TEXT,
            font=ctk.CTkFont(size=30, weight="bold")
        ).pack(padx=34, pady=(0, 14))

        self.after(1800, popup.destroy)
    def system_scan(self):
        self.clear()

        self.header(
            "SYSTEM SCAN",
            "FACIAL ANALYSIS // PLAYER STATUS"
        )

        outer = ctk.CTkFrame(
            self.page_host,
            fg_color="#040A12",
            border_width=1,
            border_color="#1E8DBB",
            corner_radius=4
        )
        outer.pack(fill="both", expand=True, padx=30, pady=(0,18))

        # Left camera/HUD side
        camera_panel = ctk.CTkFrame(
            outer,
            fg_color="#03070D",
            border_width=1,
            border_color="#12455E",
            corner_radius=3
        )
        camera_panel.pack(
            side="left", fill="both", expand=True,
            padx=16, pady=16
        )

        ctk.CTkLabel(
            camera_panel,
            text="// LIVE VISUAL FEED",
            text_color="#5DDCFF",
            font=ctk.CTkFont(size=9, weight="bold")
        ).pack(anchor="w", padx=14, pady=(10,4))

        # Canvas allows us to draw the face box and guide lines directly over video.
        self.scan_canvas = ctk.CTkCanvas(
            camera_panel,
            bg="#02060B",
            highlightthickness=1,
            highlightbackground="#14506C",
            width=650,
            height=430
        )
        self.scan_canvas.pack(fill="both", expand=True, padx=14, pady=8)

        self.scan_status = ctk.CTkLabel(
            camera_panel,
            text="SYSTEM READY",
            text_color="#78A8BC",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.scan_status.pack(pady=(4,3))

        controls = ctk.CTkFrame(
            camera_panel, fg_color="transparent"
        )
        controls.pack(pady=(5,14))

        start_button = ctk.CTkButton(
            controls,
            text="ACTIVATE CAMERA",
            fg_color=ACCENT,
            hover_color="#0878BB",
            command=self.start_camera
        )
        start_button.pack(side="left", padx=5)
        bind_hover(start_button)

        scan_button = ctk.CTkButton(
            controls,
            text="SCAN PLAYER",
            fg_color="#0C2B3B",
            hover_color="#124A62",
            border_width=1,
            border_color="#1C8EBB",
            command=self.scan_player
        )
        scan_button.pack(side="left", padx=5)
        bind_hover(scan_button)

        stop_button = ctk.CTkButton(
            controls,
            text="STOP",
            fg_color="#331722",
            hover_color="#512333",
            text_color=DANGER,
            command=self.stop_camera
        )
        stop_button.pack(side="left", padx=5)
        bind_hover(stop_button)

        # Right status side
        status_panel = ctk.CTkFrame(
            outer,
            fg_color="#06111C",
            border_width=1,
            border_color="#14506C",
            corner_radius=3,
            width=315
        )
        status_panel.pack(
            side="right", fill="y",
            padx=(0,16), pady=16
        )
        status_panel.pack_propagate(False)

        ctk.CTkLabel(
            status_panel,
            text="PLAYER ANALYSIS",
            text_color="#69E6FF",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=18, pady=(18,4))

        p = get_profile()
        self.scan_player_name = ctk.CTkLabel(
            status_panel,
            text=p["name"].upper(),
            text_color=TEXT,
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.scan_player_name.pack(anchor="w", padx=18)

        self.scan_rank = ctk.CTkLabel(
            status_panel,
            text=f"LEVEL {p['level']}  •  {p['rank']}",
            text_color=CYAN,
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.scan_rank.pack(anchor="w", padx=18, pady=(2,14))

        # Facial guide legend
        legend = ctk.CTkFrame(
            status_panel,
            fg_color="#071B27",
            border_width=1,
            border_color="#123D51",
            corner_radius=3
        )
        legend.pack(fill="x", padx=15, pady=(0,12))

        ctk.CTkLabel(
            legend,
            text="VISUAL GUIDE",
            text_color="#91CDE0",
            font=ctk.CTkFont(size=9, weight="bold")
        ).pack(anchor="w", padx=12, pady=(10,5))

        for label, desc in [
            ("JAWLINE", "lower-face guide"),
            ("CHEEKBONES", "mid-face guide"),
            ("EYE LINE", "alignment guide"),
            ("FACE BOX", "detected region"),
        ]:
            row = ctk.CTkFrame(legend, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(
                row, text=label,
                width=90,
                anchor="w",
                text_color="#65E5FF",
                font=ctk.CTkFont(size=8, weight="bold")
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=desc,
                text_color="#7598A8",
                font=ctk.CTkFont(size=8)
            ).pack(side="left")

        # Actual game stats: from ASCEND tracking database.
        self.scan_result = ctk.CTkLabel(
            status_panel,
            text=(
                "Strength\n—\n\n"
                "Intelligence\n—\n\n"
                "Social\n—\n\n"
                "Vitality\n—"
            ),
            text_color=TEXT,
            justify="left",
            anchor="w",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.scan_result.pack(fill="x", padx=18, pady=12)

        self.scan_note = ctk.CTkLabel(
            status_panel,
            text="Facial lines are visual guides only. Your attributes come from your real ASCEND activity.",
            text_color="#648595",
            wraplength=260,
            justify="left",
            font=ctk.CTkFont(size=8)
        )
        self.scan_note.pack(fill="x", padx=18, pady=(4,12))

        self.start_camera()

        if self.face_cascade is None:
            self.scan_status.configure(
                text="CAMERA ONLINE // FACE DETECTOR UNAVAILABLE",
                text_color="#F0B35A"
            )

    def start_camera(self):
        if self.camera_running:
            return

        self.camera = cv2.VideoCapture(0)

        if not self.camera.isOpened():
            self.scan_status.configure(
                text="CAMERA ERROR",
                text_color=DANGER
            )
            return

        self.camera_running = True

        self.scan_status.configure(
            text="CAMERA ONLINE // SEARCHING FOR PLAYER",
            text_color=CYAN
        )

        self.update_camera()
    def update_camera(self):
        if not self.camera_running or self.camera is None:
            return

        success, frame = self.camera.read()
        if not success:
            self.stop_camera()
            return

        frame = cv2.flip(frame, 1)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if self.face_cascade is not None:
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(100, 100)
            )
        else:
            faces = []

        # Base preview dimensions.
        frame_h, frame_w = frame.shape[:2]
        canvas_w = max(self.scan_canvas.winfo_width(), 650)
        canvas_h = max(self.scan_canvas.winfo_height(), 430)

        # Scale the webcam frame into the canvas.
        scale = min(canvas_w / frame_w, canvas_h / frame_h)
        new_w = int(frame_w * scale)
        new_h = int(frame_h * scale)
        resized = cv2.resize(frame, (new_w, new_h))

        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        image = Image.fromarray(rgb)

        self.scan_photo = ImageTk.PhotoImage(image=image)

        self.scan_canvas.delete("all")
        xoff = (canvas_w - new_w) // 2
        yoff = (canvas_h - new_h) // 2

        self.scan_canvas.create_image(
            xoff, yoff,
            anchor="nw",
            image=self.scan_photo
        )

        if len(faces) > 0:
            self.scan_status.configure(
                text="FACE DETECTED // SYSTEM LOCKED",
                text_color=GREEN
            )

        elif self.face_cascade is None:
            self.scan_status.configure(
                text="CAMERA ONLINE // FACE DETECTOR UNAVAILABLE",
                text_color="#F0B35A"
            )

        else:
            self.scan_status.configure(
                text="SEARCHING FOR PLAYER...",
                text_color=CYAN
            )

        # Draw facial analysis guides.
        for x, y, w, h in faces[:1]:
            sx = xoff + int(x * scale)
            sy = yoff + int(y * scale)
            sw = int(w * scale)
            sh = int(h * scale)

            # Outer detected face box.
            self.scan_canvas.create_rectangle(
                sx, sy, sx + sw, sy + sh,
                outline="#27D7FF",
                width=2
            )

            # Corner brackets for the HUD.
            bracket = 22
            for x1, y1, dx, dy in [
                (sx, sy, 1, 1),
                (sx+sw, sy, -1, 1),
                (sx, sy+sh, 1, -1),
                (sx+sw, sy+sh, -1, -1)
            ]:
                self.scan_canvas.create_line(
                    x1, y1, x1 + bracket*dx, y1,
                    fill="#8AEAFF", width=3
                )
                self.scan_canvas.create_line(
                    x1, y1, x1, y1 + bracket*dy,
                    fill="#8AEAFF", width=3
                )

            # Approximate visual guides based on the detected face region.
            # These are HUD overlays, not anatomical measurements.
            eye_y = sy + int(sh * 0.42)
            cheek_y = sy + int(sh * 0.58)
            jaw_y = sy + int(sh * 0.82)
            center_x = sx + sw // 2

            # Eye line
            self.scan_canvas.create_line(
                sx + int(sw*0.14), eye_y,
                sx + int(sw*0.86), eye_y,
                fill="#C7F6FF", width=1, dash=(5,4)
            )
            self.scan_canvas.create_text(
                sx + 8, eye_y - 8,
                text="EYE LINE",
                anchor="w",
                fill="#9EEBFF",
                font=("Segoe UI", 8, "bold")
            )

            # Cheekbone guide: two angular lines.
            self.scan_canvas.create_line(
                sx + int(sw*0.12), cheek_y,
                center_x - int(sw*0.07), cheek_y - int(sh*0.025),
                fill="#63E2FF", width=2
            )
            self.scan_canvas.create_line(
                center_x + int(sw*0.07), cheek_y - int(sh*0.025),
                sx + int(sw*0.88), cheek_y,
                fill="#63E2FF", width=2
            )
            self.scan_canvas.create_text(
                sx + 8, cheek_y - 8,
                text="CHEEKBONES",
                anchor="w",
                fill="#63E2FF",
                font=("Segoe UI", 8, "bold")
            )

            # Jawline guide: two lower-face segments.
            self.scan_canvas.create_line(
                sx + int(sw*0.20), jaw_y,
                center_x - int(sw*0.07), sy + int(sh*0.94),
                fill="#9B8CFF", width=2
            )
            self.scan_canvas.create_line(
                center_x + int(sw*0.07), sy + int(sh*0.94),
                sx + int(sw*0.80), jaw_y,
                fill="#9B8CFF", width=2
            )
            self.scan_canvas.create_text(
                sx + 8, sy + sh - 10,
                text="JAWLINE",
                anchor="w",
                fill="#B5A8FF",
                font=("Segoe UI", 8, "bold")
            )

            # Center scan line.
            self.scan_canvas.create_line(
                center_x, sy - 12,
                center_x, sy + sh + 12,
                fill="#2CCEFF", width=1, dash=(4,5)
            )

        self.after(30, self.update_camera)

    def scan_player(self):
        if not self.camera_running:
            return

        success, frame = self.camera.read()
        if not success:
            return

        frame = cv2.flip(frame, 1)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        if self.face_cascade is not None:
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(100, 100)
            )
        else:
            faces = [(0, 0, 1, 1)]

        if self.face_cascade is not None and len(faces) == 0:
            self.scan_status.configure(
                text="SCAN FAILED // FACE NOT DETECTED",
                text_color=DANGER
            )
            return

        profile = get_profile()
        stats = stat_totals()

        strength = max(1, min(99, stats.get("STR", 0) // 10))
        intelligence = max(1, min(99, stats.get("INT", 0) // 10))
        social = max(1, min(99, stats.get("SOC", 0) // 10))

        # Vitality is a consistency/activity stat in the current prototype.
        workout = stats.get("STR", 0)
        vitality = max(1, min(99, workout // 14))

        self.scan_status.configure(
            text="SCAN COMPLETE // PLAYER IDENTIFIED",
            text_color=GREEN
        )

        self.scan_player_name.configure(
            text=profile["name"].upper()
        )
        self.scan_rank.configure(
            text=f"LEVEL {profile['level']}  •  {profile['rank']}"
        )

        self.scan_result.configure(
            text=(
                f"Strength              {strength:>2}\n\n"
                f"Intelligence          {intelligence:>2}\n\n"
                f"Social                {social:>2}\n\n"
                f"Vitality              {vitality:>2}\n\n"
                f"Total Experience      {profile['xp']}\n"
                f"Arena Power           {profile['arena_points']} AP"
            )
        )

    def stop_camera(self):

        self.camera_running = False

        if self.camera is not None:

            self.camera.release()
            self.camera = None

        if hasattr(self, "camera_label"):

            self.camera_label.configure(
                image=None,
                text="CAMERA OFFLINE"
            )
    
    def status(self):
        self.clear()
        self.header("STATUS", "PLAYER STATUS // SYSTEM DATA")

        p=get_profile()
        stats=stat_totals()

        panel=self.holo_panel(self.page_host)
        panel.pack(fill="both",expand=True,padx=35,pady=(0,18))

        top=ctk.CTkFrame(panel,fg_color="transparent")
        top.pack(fill="x",padx=22,pady=(18,8))

        identity=ctk.CTkFrame(top,fg_color="transparent")
        identity.pack(side="left",fill="x",expand=True)

        ctk.CTkLabel(
            identity,text=p["name"].upper(),
            text_color="#EAF8FF",
            font=ctk.CTkFont(size=26,weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            identity,
            text=f"LEVEL {p['level']}     RANK {p['rank']}",
            text_color="#57C7F7",
            font=ctk.CTkFont(size=12,weight="bold")
        ).pack(anchor="w",pady=(2,0))

        ctk.CTkLabel(
            identity,
            text=f"PLAYER ID  {p['player_id']}",
            text_color="#6D8090",
            font=ctk.CTkFont(size=9)
        ).pack(anchor="w",pady=(4,0))

        ctk.CTkLabel(
            top,text="STATUS // ONLINE",
            text_color=GREEN,
            font=ctk.CTkFont(size=10,weight="bold")
        ).pack(side="right",anchor="n")

        # Circular level meter
        meter_host=ctk.CTkFrame(panel,fg_color="transparent")
        meter_host.pack(pady=(2,8))

        meter=CircularMeter(meter_host,220,13)
        meter.pack()

        current=p["xp"]
        level=1
        while current >= 250+(level-1)*100:
            current -= 250+(level-1)*100
            level += 1
        needed=250+(level-1)*100
        self.after(FPS,lambda:self.meter(meter,current/needed))

        ctk.CTkLabel(
            panel,text=f"LEVEL {p['level']}  •  {p['xp']} XP",
            text_color=TEXT,
            font=ctk.CTkFont(size=13,weight="bold")
        ).pack()

        stat_box=self.holo_panel(panel)
        stat_box.pack(fill="x",padx=22,pady=(14,18))

        ctk.CTkLabel(
            stat_box,text="ATTRIBUTES",
            text_color="#9FD9EF",
            font=ctk.CTkFont(size=11,weight="bold")
        ).pack(anchor="w",padx=18,pady=(12,3))

        circles=ctk.CTkFrame(stat_box,fg_color="transparent")
        circles.pack(fill="x",padx=10,pady=8)

        attrs=[
            ("STR","STRENGTH",stats.get("STR",0)),
            ("INT","INTELLIGENCE",stats.get("INT",0)),
            ("SOC","SOCIAL",stats.get("SOC",0)),
        ]
        for i,(code,name,value) in enumerate(attrs):
            item=self.circular_stat(
                circles,code,name,
                max(1,min(99,value//10+1)),
                100,110
            )
            item.grid(row=0,column=i,padx=18,pady=5)
            circles.grid_columnconfigure(i,weight=1)

    def study_history(self):
        self.header("STUDY HISTORY", "INTELLIGENCE PROGRESSION // FOCUS TIMELINE")
        rows=[]
        try:
            con=__import__("sqlite3").connect("ascend.db")
            con.row_factory=__import__("sqlite3").Row
            rows=con.execute(
                "SELECT log_time,item,value,unit FROM logs WHERE category='Study' ORDER BY id ASC"
            ).fetchall()
            con.close()
        except Exception:
            rows=[]
        total_hours=sum(float(r["value"]) for r in rows)
        sessions=len(rows)
        best=max((float(r["value"]) for r in rows),default=0)

        top=ctk.CTkFrame(self.page_host,fg_color="transparent")
        top.pack(fill="x",padx=35,pady=(0,10))
        for title,value,sub in [
            ("SESSIONS",str(sessions),"study sessions"),
            ("TOTAL",f"{total_hours:g} h","lifetime study"),
            ("BEST",f"{best:g} h","longest single session")
        ]:
            f=self.holo_panel(top);f.pack(side="left",fill="x",expand=True,padx=5)
            ctk.CTkLabel(f,text=title,text_color=MUTED).pack(anchor="w",padx=18,pady=(15,2))
            ctk.CTkLabel(f,text=value,text_color="#54C8F6",font=ctk.CTkFont(size=23,weight="bold")).pack(anchor="w",padx=18)
            ctk.CTkLabel(f,text=sub,text_color=MUTED).pack(anchor="w",padx=18,pady=(0,15))
        ctk.CTkLabel(self.page_host,text="FOCUS TIMELINE",text_color="#A9DFF2",
                     font=ctk.CTkFont(size=13,weight="bold")).pack(anchor="w",padx=35,pady=(10,6))
        if not rows:
            ctk.CTkLabel(self.page_host,text="No study sessions yet. Log study time from LOG ACTIVITY.",
                         text_color=MUTED).pack(anchor="w",padx=35)
            return
        for row in reversed(rows[-20:]):
            f=self.holo_panel(self.page_host);f.pack(fill="x",padx=35,pady=3)
            ctk.CTkLabel(f,text=(row["log_time"] or "")[:10],width=95,text_color="#6D8090").pack(side="left",padx=12,pady=9)
            ctk.CTkLabel(f,text=row["item"],text_color=TEXT).pack(side="left")
            ctk.CTkLabel(f,text=f"{float(row['value']):g} h",text_color="#54C8F6",
                         font=ctk.CTkFont(weight="bold")).pack(side="right",padx=14)


    def social_history(self):
        self.header("SOCIAL HISTORY", "SOCIAL ATTRIBUTE // CONTACT TIMELINE")
        try:
            from database import logs_for_category
            all_rows = logs_for_category("Social", days=3650)
        except Exception:
            all_rows = []

        total_people = sum(float(r["value"]) for r in all_rows)
        sessions = len(all_rows)
        best = max((float(r["value"]) for r in all_rows), default=0)

        top = ctk.CTkFrame(self.page_host, fg_color="transparent")
        top.pack(fill="x", padx=35, pady=(0, 10))
        for title, value, sub in [
            ("SESSIONS", str(sessions), "social logs"),
            ("TOTAL", f"{total_people:g}", "people talked to"),
            ("BEST DAY", f"{best:g}", "most in one log"),
        ]:
            f = self.holo_panel(top)
            f.pack(side="left", fill="x", expand=True, padx=5)
            ctk.CTkLabel(f, text=title, text_color=MUTED).pack(anchor="w", padx=18, pady=(15, 2))
            ctk.CTkLabel(f, text=value, text_color="#54C8F6",
                         font=ctk.CTkFont(size=23, weight="bold")).pack(anchor="w", padx=18)
            ctk.CTkLabel(f, text=sub, text_color=MUTED).pack(anchor="w", padx=18, pady=(0, 15))

        ctk.CTkLabel(
            self.page_host, text="INTERACTION TIMELINE", text_color="#A9DFF2",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=35, pady=(10, 6))

        if not all_rows:
            ctk.CTkLabel(
                self.page_host,
                text="No social sessions yet. Your Social stat is waiting.",
                text_color=MUTED
            ).pack(anchor="w", padx=35)
            return

        for row in reversed(all_rows[-15:]):
            f = self.holo_panel(self.page_host)
            f.pack(fill="x", padx=35, pady=3)
            ctk.CTkLabel(
                f, text=row["log_time"][:10], width=95,
                text_color="#6D8090"
            ).pack(side="left", padx=12, pady=9)
            ctk.CTkLabel(
                f, text=row["item"], text_color=TEXT
            ).pack(side="left")
            ctk.CTkLabel(
                f, text=f"{row['value']:g} people",
                text_color="#54C8F6",
                font=ctk.CTkFont(weight="bold")
            ).pack(side="right", padx=14)

    def history(self):
        self.header("GYM HISTORY", "STRENGTH PROGRESSION // LIFT TIMELINE")
        try:
            rows = gym_history()
            s = gym_summary()
        except Exception:
            rows = []
            s = {"sessions": 0, "best_weight": 0, "first_weight": 0, "improvement": 0}

        if not rows:
            try:
                con = __import__("sqlite3").connect("ascend.db")
                con.row_factory = __import__("sqlite3").Row
                rows = con.execute(
                    "SELECT log_time,item,value,unit FROM logs WHERE category='Gym' ORDER BY id ASC"
                ).fetchall()
                con.close()
                weights=[float(r["value"]) for r in rows if r["unit"]=="kg"]
                if weights:
                    s={"sessions":len(rows),"best_weight":max(weights),
                       "first_weight":weights[0],"improvement":max(weights)-weights[0]}
            except Exception:
                rows=[]

        top=ctk.CTkFrame(self.page_host,fg_color="transparent")
        top.pack(fill="x",padx=35)
        for title,value,sub,col in [
            ("SESSIONS",str(s["sessions"]),"workouts logged","#F4F6FF"),
            ("BEST WEIGHT",f"{s['best_weight']:g} kg","highest logged weight","#54C8F6"),
            ("IMPROVEMENT",f"+{s['improvement']:g} kg","best vs first","#4ADE80")
        ]:
            f=self.holo_panel(top);f.pack(side="left",fill="x",expand=True,padx=5)
            ctk.CTkLabel(f,text=title,text_color=MUTED).pack(anchor="w",padx=18,pady=(15,2))
            ctk.CTkLabel(f,text=value,text_color=col,font=ctk.CTkFont(size=23,weight="bold")).pack(anchor="w",padx=18)
            ctk.CTkLabel(f,text=sub,text_color=MUTED).pack(anchor="w",padx=18,pady=(0,15))

        ctk.CTkLabel(self.page_host,text="LIFT TIMELINE",text_color="#A9DFF2",
                     font=ctk.CTkFont(size=13,weight="bold")).pack(anchor="w",padx=35,pady=(18,6))
        if not rows:
            ctk.CTkLabel(self.page_host,text="No workouts yet. Log a workout from LOG ACTIVITY.",
                         text_color=MUTED).pack(anchor="w",padx=35)
            return
        for row in reversed(rows[-20:]):
            f=self.holo_panel(self.page_host);f.pack(fill="x",padx=35,pady=3)
            ctk.CTkLabel(f,text=(row["log_time"] or "")[:10],width=95,text_color="#6D8090").pack(side="left",padx=12,pady=9)
            ctk.CTkLabel(f,text=row["item"],text_color=TEXT).pack(side="left")
            ctk.CTkLabel(f,text=f"{float(row['value']):g} kg",text_color="#54C8F6",
                         font=ctk.CTkFont(weight="bold")).pack(side="right",padx=14)


    def profile(self):
        self.header("PROFILE","IDENTITY // PERSONAL PROGRESSION")

        p=get_profile()

        card=ctk.CTkFrame(
            self.page_host,fg_color="#071521",
            border_width=1,border_color="#1E8DBB",corner_radius=3
        )
        card.pack(fill="x",padx=35,pady=(0,12))

        left=ctk.CTkFrame(card,fg_color="transparent")
        left.pack(side="left",fill="x",expand=True,padx=22,pady=18)

        ctk.CTkLabel(
            left,text="YOUR PROFILE",text_color="#63DFFF",
            font=ctk.CTkFont(size=11,weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            left,text=p["name"],text_color=TEXT,
            font=ctk.CTkFont(size=32,weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            left,text=f"LEVEL {p['level']}   •   {p['rank']}   •   {p['xp']} XP",
            text_color=CYAN,
            font=ctk.CTkFont(size=12,weight="bold")
        ).pack(anchor="w",pady=(6,0))

        ctk.CTkButton(
            left,text="CHANGE NAME",width=160,
            fg_color=ACCENT,hover_color="#0878BB",
            command=self.name_dialog
        ).pack(anchor="w",pady=(12,0))

        # Badge panel
        badge_panel=ctk.CTkFrame(
            card,fg_color="#06101A",
            border_width=1,border_color="#163B4E",
            corner_radius=3,width=245
        )
        badge_panel.pack(side="right",fill="y",padx=18,pady=18)

        ctk.CTkLabel(
            badge_panel,text="BADGE COLLECTION",
            text_color="#63DFFF",
            font=ctk.CTkFont(size=10,weight="bold")
        ).pack(pady=(14,8))

        badge_ranks=["E-RANK","D-RANK","C-RANK","B-RANK","A-RANK","S-RANK","NATIONAL"]
        current_rank=p["rank"]

        for badge_rank in badge_ranks:
            unlocked=badge_unlocked(badge_rank,current_rank)
            label_text=f"✓ {badge_rank}  •  EQUIP" if unlocked else f"🔒 {badge_rank}  •  LOCKED"
            text_color="#63DFFF" if unlocked else "#4E6370"

            button=ctk.CTkButton(
                badge_panel,
                text=label_text,
                height=28,
                fg_color="#0B2A3B" if unlocked else "#08131C",
                hover_color="#124A62" if unlocked else "#08131C",
                text_color=text_color,
                state="normal" if unlocked else "disabled",
                command=(lambda r=badge_rank:self.equip_badge_ui(r)) if unlocked else None
            )
            button.pack(fill="x",padx=12,pady=3)
            bind_hover(button)

        ctk.CTkLabel(
            self.page_host,
            text="Badges unlock permanently as you reach higher progression ranks. Replace the PNG files in assets/badges/ with your own artwork.",
            text_color="#7898A8",
            wraplength=800,
            justify="left"
        ).pack(anchor="w",padx=35,pady=(4,0))

    def equip_badge_ui(self,badge_rank):
        if equip_badge(badge_rank):
            play_sound("click.wav")

            # Equipped rank badge becomes the sidebar PFP.
            if hasattr(self, "profile_image") and hasattr(self, "pfp_label"):
                self.profile_image = self.load_profile_image()
                self.pfp_label.configure(
                    image=self.profile_image,
                    text="" if self.profile_image else "?"
                )

            self.update_badge_avatar()
            self.show_page("profile")

    def arena(self):
        self.header("ARENA","Compete with other players using a separate PvP rating.")
        p=get_profile()
        ctk.CTkLabel(self.page_host,text=f"PLAYER  {p['name']}    •    ID  {p['player_id']}",
                     text_color=TEXT,font=ctk.CTkFont(size=13,weight="bold")).pack(anchor="w",padx=35)
        card=ctk.CTkFrame(self.page_host,fg_color=PANEL,corner_radius=4);card.pack(fill="x",padx=35,pady=15)
        ctk.CTkLabel(card,text="ARENA RATING",text_color=MUTED).pack(pady=(18,2))
        ctk.CTkLabel(card,text=f"{p['arena_points']} AP",text_color=CYAN,
                     font=ctk.CTkFont(size=36,weight="bold")).pack()
        ctk.CTkLabel(card,text="Competitive rank is separate from your E→S progression rank.",
                     text_color=MUTED).pack(pady=(2,18))
        ranks=[(0,"BRONZE"),(1100,"SILVER"),(1300,"GOLD"),(1500,"PLATINUM"),(1800,"DIAMOND"),(2200,"ASCENDED")]
        arank="BRONZE"
        for minimum,name in ranks:
            if p["arena_points"]>=minimum:arank=name
        ctk.CTkLabel(self.page_host,text=f"YOUR ARENA RANK  •  {arank}",text_color=ACCENT,
                     font=ctk.CTkFont(size=20,weight="bold")).pack(anchor="w",padx=35,pady=8)
        ctk.CTkLabel(self.page_host,text="MULTIPLAYER BACKEND SETUP",text_color=TEXT,
                     font=ctk.CTkFont(size=15,weight="bold")).pack(anchor="w",padx=35,pady=(25,5))
        ctk.CTkLabel(self.page_host,text="This desktop build is ready for online leaderboard integration. "
                     "Each install has a unique Player ID and Arena rating. "
                     "For the hackathon, connect a shared backend (Supabase/Firebase) so all clients write to the same leaderboard.",
                     text_color=MUTED,wraplength=760,justify="left").pack(anchor="w",padx=35)
        if ctk.CTkButton:
            ctk.CTkButton(self.page_host,text="SET PLAYER NAME",fg_color=ACCENT,command=self.name_dialog).pack(anchor="w",padx=35,pady=18)

    def name_dialog(self):
        overlay,panel=self.make_overlay(450,300)
        panel.configure(border_width=1,border_color="#29BFFF")

        ctk.CTkLabel(
            panel,text="PLAYER IDENTITY",
            text_color=CYAN,
            font=ctk.CTkFont(size=21,weight="bold")
        ).pack(pady=(26,5))

        ctk.CTkLabel(
            panel,
            text="This name appears on your profile and Arena.",
            text_color=MUTED
        ).pack(pady=(0,10))

        entry=ctk.CTkEntry(panel,height=38)
        entry.pack(fill="x",padx=42,pady=10)
        entry.insert(0,get_profile()["name"] or "Player")
        entry.select_range(0,"end")
        entry.focus_set()

        error=ctk.CTkLabel(panel,text="",text_color=DANGER)
        error.pack()

        def save():
            name=entry.get().strip()
            if len(name)<2:
                error.configure(text="Use at least 2 characters.")
                return
            if len(name)>20:
                error.configure(text="Maximum 20 characters.")
                return
            if set_name(name):
                overlay.destroy()
                if hasattr(self, "sidebar_name"):
                    p = get_profile()
                    self.sidebar_name.configure(text=p["name"])
                    self.sidebar_rank.configure(text=p["rank"])
                self.show_page("profile")
            else:
                error.configure(text="Could not save the name.")

        ctk.CTkButton(
            panel,text="SAVE NAME",
            fg_color=ACCENT,hover_color="#0878BB",
            command=save
        ).pack(pady=12)

        ctk.CTkButton(
            panel,text="CANCEL",
            fg_color="transparent",
            border_width=1,
            border_color="#35586D",
            text_color=MUTED,
            command=overlay.destroy
        ).pack()

        entry.bind("<Return>",lambda e:save())
        entry.bind("<Escape>",lambda e:overlay.destroy())

