import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json
from validator import Validator
from database import NarrativeDB
import sys
import os
import time
import subprocess
import requests

db = NarrativeDB()
validator = Validator(db)


root = tk.Tk()
root.title("서사 정합성 검증기")
root.geometry("900x700")

# 캐릭터 추가
frame_top = tk.Frame(root)
frame_top.pack(pady=10)

tk.Label(frame_top, text="캐릭터 이름:").pack(side=tk.LEFT)
entry_char = tk.Entry(frame_top)
entry_char.pack(side=tk.LEFT, padx=5)

def add_character():
    name = entry_char.get()
    if name:
        db.add_character(name)
        update_char_checkboxes()
        messagebox.showinfo("완료", f"{name} 추가됨")

tk.Button(frame_top, text="캐릭터 추가", command=add_character).pack(side=tk.LEFT)

frame_mid = tk.Frame(root)
frame_mid.pack(pady=10)

tk.Label(frame_mid, text="등장 캐릭터:").pack(side=tk.LEFT)

char_vars = {}  # 캐릭터별 체크박스 변수 저장
char_alias_entries = {}  # 캐릭터별 호칭 입력창

def update_char_checkboxes():
    for widget in frame_mid.winfo_children():
        if not isinstance(widget, tk.Label):
            widget.destroy()
    
    char_alias_entries.clear()
    
    for name in db.characters.keys():
        if name not in char_vars:
            char_vars[name] = tk.BooleanVar()
        
        row = tk.Frame(frame_mid)
        row.pack(side=tk.LEFT, padx=5)
        
        ttk.Checkbutton(row, text=name, variable=char_vars[name]).pack(side=tk.LEFT)
        
        alias_entry = tk.Entry(row, width=15)
        alias_entry.insert(0, ", ".join(db.get_aliases(name)))
        alias_entry.pack(side=tk.LEFT, padx=3)
        
        char_alias_entries[name] = alias_entry

def get_selected_characters():
    # 선택된 캐릭터 목록 반환하면서 호칭도 업데이트
    selected = []
    for name, var in char_vars.items():
        if var.get():
            selected.append(name)
            # 호칭 입력창에서 최신 호칭 가져와서 업데이트
            if name in char_alias_entries:
                raw = char_alias_entries[name].get()
                aliases = [a.strip() for a in raw.split(",") if a.strip()]
                db.update_aliases(name, aliases)
    return selected

def get_selected_characters():
    return [name for name, var in char_vars.items() if var.get()]
# 장면 입력
tk.Label(root, text="장면 입력:").pack()
text_scene = scrolledtext.ScrolledText(root, height=6)
text_scene.pack(padx=10, pady=5, fill=tk.X)

# 분류 결과 표시 프레임
tk.Label(root, text="문장 분류 (수정 가능):").pack()
frame_classify = tk.Frame(root)
frame_classify.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

canvas = tk.Canvas(frame_classify)
scrollbar = ttk.Scrollbar(frame_classify, orient="vertical", command=canvas.yview)
scroll_frame = tk.Frame(canvas)

scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

classify_rows = []  # 분류 결과 저장

def show_classify():
    scene = text_scene.get("1.0", tk.END).strip()
    characters = get_selected_characters()
    if not scene or not characters:
        messagebox.showwarning("경고", "캐릭터와 장면을 입력해주세요")
        return

    for widget in scroll_frame.winfo_children():
        widget.destroy()
    classify_rows.clear()

    # 캐릭터 + 호칭 정보 포함해서 분류
    char_info = {name: db.get_aliases(name) for name in characters}
    raw = validator.classify(scene, char_info)

    try:
        data = json.loads(raw)
    except:
        messagebox.showerror("오류", "분류 결과 파싱 실패")
        return

    for i, item in enumerate(data):
        row_frame = tk.Frame(scroll_frame)
        row_frame.pack(fill=tk.X, pady=2)

        tk.Label(row_frame, text=item["문장"], wraplength=400, anchor="w").pack(side=tk.LEFT, padx=5)

        raw_class = item["분류"]
        if "_" in raw_class:
            char_val, attr_val = raw_class.rsplit("_", 1)
        else:
            char_val, attr_val = "", raw_class

        combo_attr = ttk.Combobox(row_frame, values=["W", "P", "B", "K", "D"], width=5)
        combo_attr.set(attr_val)
        combo_attr.pack(side=tk.LEFT, padx=5)

        combo_char_row = ttk.Combobox(row_frame, values=list(db.characters.keys()), width=10)
        combo_char_row.set(char_val)
        combo_char_row.pack(side=tk.LEFT, padx=5)

    # 분류 옵션 생성
    options = ["W"]
    for name in characters:
        for attr in ["P", "B", "K", "D"]:
            options.append(f"{name}_{attr}")

    # 각 문장마다 드롭다운 생성
    for i, item in enumerate(data):
        row_frame = tk.Frame(scroll_frame)
        row_frame.pack(fill=tk.X, pady=2)

        tk.Label(row_frame, text=item["문장"], wraplength=400, anchor="w").pack(side=tk.LEFT, padx=5)

        # 분류값 파싱 (예: "홍길동_P" → attr="P", char="홍길동")
        raw_class = item["분류"]
        if "_" in raw_class:
            char_val, attr_val = raw_class.rsplit("_", 1)
        else:
            char_val, attr_val = "", raw_class  # W인 경우

        # 속성 드롭다운
        combo_attr = ttk.Combobox(row_frame, values=["W", "P", "B", "K", "D"], width=5)
        combo_attr.set(attr_val)
        combo_attr.pack(side=tk.LEFT, padx=5)

        # 캐릭터 드롭다운
        combo_char_row = ttk.Combobox(row_frame, values=list(db.characters.keys()), width=10)
        combo_char_row.set(char_val)
        combo_char_row.pack(side=tk.LEFT, padx=5)

        # W면 캐릭터 드롭다운 비활성화
        def on_attr_change(event, c=combo_char_row, a=combo_attr):
            if a.get() == "W":
                c.set("")
                c.config(state="disabled")
            else:
                c.config(state="normal")

        combo_attr.bind("<<ComboboxSelected>>", on_attr_change)
        if attr_val == "W":
            combo_char_row.config(state="disabled")

        classify_rows.append((item["문장"], combo_attr, combo_char_row))

tk.Button(root, text="자동 분류", command=show_classify).pack(pady=5)

# 검증 버튼
def validate():
    character = get_selected_characters()
    scene = text_scene.get("1.0", tk.END).strip()
    if not character or not scene:
        messagebox.showwarning("경고", "캐릭터와 장면을 입력해주세요")
        return
    result = validator.validate(character, scene)
    if result["status"] == "pass":
        text_result.config(state=tk.NORMAL)
        text_result.delete("1.0", tk.END)
        text_result.insert(tk.END, "✅ 정합")
        text_result.config(state=tk.DISABLED)
    else:
        text_result.config(state=tk.NORMAL)
        text_result.delete("1.0", tk.END)
        text_result.insert(tk.END, f"❌ 비정합\n실패 항목: {result['failed_at']}\n이유: {result['reason']}")
        text_result.config(state=tk.DISABLED)

tk.Button(root, text="검증", command=validate).pack(pady=5)

# 결과 출력
tk.Label(root, text="결과:").pack()
text_result = scrolledtext.ScrolledText(root, height=5, state=tk.DISABLED)
text_result.pack(padx=10, pady=5, fill=tk.X)

root.mainloop()