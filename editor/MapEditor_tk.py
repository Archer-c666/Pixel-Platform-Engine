import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageDraw,ImageTk, ImageOps

DEFAULT_MAP = {
    "name": "关卡1",
    "width": 2000,
    "height": 640,
    "tiles": []
}

def snap(v, cell):
    return (v // cell) * cell



class PropertyDialog(simpledialog.Dialog):
    def __init__(self, parent, title, fields: dict):
        self.fields = fields
        super().__init__(parent, title)

    def body(self, master):
        self.entries = {}
        row = 0
        for k, v in self.fields.items():
            ttk.Label(master, text=k).grid(row=row, column=0, sticky="w", padx=6, pady=4)
            e = ttk.Entry(master)
            e.grid(row=row, column=1, padx=6, pady=4)
            e.insert(0, str(v) if v is not None else "")
            self.entries[k] = e
            row += 1
        return list(self.entries.values())[0] if self.entries else None

    def apply(self):
        for k, e in self.entries.items():
            val = e.get().strip()
            if val.isdigit():
                self.fields[k] = int(val)
            else:
                try:
                    self.fields[k] = float(val)
                except:
                    self.fields[k] = val

class LevelEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("2D 像素地图编辑器 ")
        self.geometry("1200x720")
        #系统自带的默认MAP
        self.map = DEFAULT_MAP.copy()
        self.map['tiles'] = []
        self.map['entities'] = []

        self.grid_cell = 32
        self.images: dict[str, ImageTk.PhotoImage] = {}

        self.current_tool = tk.StringVar(value="solid")
        self.is_drawing = False
        self.drag_start = None
        self.preview_rect = None
        self.selected_item = None
        self.n = 0   #路径列表 图像选取计数

        self.selected_image = ""
        self.selected_image_preview_default_obj = ImageTk.PhotoImage(Image.new("RGB", (self.grid_cell, self.grid_cell), color=(100, 100, 100)))
        self.selected_image_preview_obj = self.selected_image_preview_default_obj
    
        self.create_widgets()
        self.draw_grid()
        self.bind_events()

    def change_image_selected(self, event):
        selected_image = self.image_combobox.get()
        self.selected_image_preview_obj = self.images[selected_image]
        self.image_preview_lb.configure(image=self.selected_image_preview_obj)
        self.selected_image = selected_image

    def create_widgets(self):           #创建窗口小组件
        ctrl = ttk.Frame(self)
        ctrl.pack(side="top", fill="x")

        # 添加像素图像按钮
        tools = ttk.Frame(self)
        tools.pack(side="top", fill="x", pady=6)
        ttk.Button(tools, text="加载像素图像", command=self.load_image).pack(side="left", padx=6)


        self.image_combobox = ttk.Combobox(tools)
        self.image_combobox.bind("<<ComboboxSelected>>", self.change_image_selected)
        self.image_combobox.pack(side="left", padx=10)


        self.image_preview_lb = ttk.Label(tools, image=self.selected_image_preview_obj)
        self.image_preview_lb.pack(side="left", padx=10)

        ttk.Label(ctrl, text="地图名称").pack(side="left", padx=4)
        self.name_var = tk.StringVar(value=self.map['name'])
        ttk.Entry(ctrl, textvariable=self.name_var, width=16).pack(side="left", padx=4)

        ttk.Label(ctrl, text="宽度").pack(side="left", padx=4)
        self.width_var = tk.IntVar(value=self.map['width'])
        ttk.Entry(ctrl, textvariable=self.width_var, width=6).pack(side="left", padx=4)

        ttk.Label(ctrl, text="高度").pack(side="left", padx=4)
        self.height_var = tk.IntVar(value=self.map['height'])
        ttk.Entry(ctrl, textvariable=self.height_var, width=6).pack(side="left", padx=4)

        ttk.Label(ctrl, text="格子大小").pack(side="left", padx=4)
        self.grid_var = tk.IntVar(value=self.grid_cell)
        ttk.Entry(ctrl, textvariable=self.grid_var, width=4).pack(side="left", padx=4)

        ttk.Button(ctrl, text="应用地图设置", command=self.apply_map_settings).pack(side="left", padx=8)

        tools = ttk.Frame(self)
        tools.pack(side="top", fill="x", pady=6)
        tool_names = {
            "no_collide_image":"非碰撞图像",
            "collide_image": "碰撞图像",
            "water": "水域",
            "solid": "地形块",
            "player": "玩家",
            "enemy": "敌人",
            "item": "物品",
            "door": "传送门",
            "boss": "Boss",
            "select": "选择",
        }
        for t in ["no_collide_image","collide_image", "water", "solid", "player", "enemy", "item", "door", "boss", "select"]:
            rb = ttk.Radiobutton(tools, text=tool_names[t], value=t, variable=self.current_tool)
            rb.pack(side="left", padx=6)

        ttk.Button(tools, text="加载 JSON", command=self.load_json).pack(side="right", padx=6)
        ttk.Button(tools, text="导出 PNG 预览", command=self.export_png).pack(side="right", padx=6)
        ttk.Button(tools, text="导出 JSON", command=self.export_json).pack(side="right", padx=6)

        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(side="top", fill="both", expand=True)

        self.hbar = ttk.Scrollbar(canvas_frame, orient="horizontal")          #设置滚动条
        self.hbar.pack(side="bottom", fill="x")
        self.vbar = ttk.Scrollbar(canvas_frame, orient="vertical")
        self.vbar.pack(side="right", fill="y")

        #bg为背景颜色设置参数 '#222'为16进制RGB颜色缩写
        self.canvas = tk.Canvas(canvas_frame, bg="#222", xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.hbar.config(command=self.canvas.xview)
        self.vbar.config(command=self.canvas.yview)

        status = ttk.Frame(self)
        status.pack(side="bottom", fill="x")
        self.status_label = ttk.Label(status, text="工具: 地形块 | 格子: 32px")
        self.status_label.pack(side="left")

    def load_image(self):
        # 弹出文件选择框加载图像
        file_path = filedialog.askopenfilename(filetypes=[("PNG 文件", "*.png")])
        if not file_path:
            return
        try:
            if file_path not in self.images.keys():
                self.n += 1
                img = Image.open(file_path)
                img = img.convert("RGBA")  # 确保是 RGBA 模式
                img.thumbnail((self.grid_cell, self.grid_cell))  # 调整大小以适应网格
                img_tk = ImageTk.PhotoImage(img)
                self.images[file_path] = img_tk
                self.selected_image = file_path
                self.image_combobox['values'] = list(self.images.keys())
                messagebox.showinfo("成功", f"已加载图像：{file_path}")
            else:
                messagebox.showwarning("提示", f"请无重复加载图像")
        except Exception as e:
            messagebox.showerror("错误", f"加载图像失败: {e}")

    def bind_events(self):
        self.canvas.bind("<ButtonPress-1>", self.on_left_down)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_up)
        self.canvas.bind("<ButtonPress-3>", self.on_right_down)
        self.bind("<Delete>", self.on_delete)
        self.current_tool.trace_add("write", lambda *a: self.update_status())

    def update_status(self):
        tool_names = {
            "no_collide_image": "非碰撞实体",
            "collide_image": "碰撞实体",
            "water":"水域",
            "solid": "地形块",
            "enemy": "敌人",
            "item": "道具",
            "door": "传送门",
            "boss": "Boss",
            "select": "选择"
        }
        self.status_label.config(text=f"工具: {tool_names[self.current_tool.get()]} | 格子: {self.grid_cell}px")

    def apply_map_settings(self):
        try:
            w = int(self.width_var.get())
            h = int(self.height_var.get())
            g = int(self.grid_var.get())
            if w <= 0 or h <= 0 or g <= 0:
                raise ValueError()
        except:
            messagebox.showerror("错误", "宽度、高度和格子大小必须为正整数。")
            return
        self.map['width'] = w
        self.map['height'] = h
        self.grid_cell = g
        self.draw_grid()
        self.update_status()

    def draw_grid(self):            #绘制网格
        self.canvas.delete("all")
        w = self.map['width']
        h = self.map['height']
        cell = self.grid_cell
        self.canvas.config(scrollregion=(0, 0, w, h))
        for x in range(0, w, cell):
            self.canvas.create_line(x, 0, x, h, fill="#333")
        for y in range(0, h, cell):
            self.canvas.create_line(0, y, w, y, fill="#333")
        for t in self.map['tiles']:
            self.draw_tile_on_canvas(t)

    def draw_tile_on_canvas(self, t):
        if t['type'] == "no_collide_image":
            # 绘制图像
            img_path = t['path']
            img_tk = self.images[img_path]
            img_id = self.canvas.create_image(t['x'], t['y'], image=img_tk,anchor = 'nw')
            t['_canvas_id'] = img_id

        elif t['type'] == "collide_image":
            # 绘制图像
            img_path = t['path']
            img_tk = self.images[img_path]
            img_id = self.canvas.create_image(t['x'], t['y'], image=img_tk,anchor = 'nw')
            t['_canvas_id'] = img_id
        
        elif t['type'] == "water":
            # 绘制图像
            img_path = t['path']
            img_tk = self.images[img_path]
            img_id = self.canvas.create_image(t['x'], t['y'], image=img_tk,anchor = 'nw')
            t['_canvas_id'] = img_id

        elif t['type'] == 'solid':
            cid = self.canvas.create_rectangle(t['x'], t['y'], t['x'] + t['w'], t['y'] + t['h'],
                                               fill="#777", outline="#ccc")
            t['_canvas_id'] = cid

        #entity绘制
        else:
            r = max(4, self.grid_cell // 3)
            color_map = {'enemy': "#d9534f", 'item': "#5bc0de", 'door': "#f0ad4e", 'boss': "#5cb85c"}
            cid = self.canvas.create_oval(t['x'] - r, t['y'] - r, t['x'] + r, t['y'] + r,
                                          fill=color_map.get(t['type'], "#fff"), outline="#000")
            t['_canvas_id'] = cid

    #鼠标操控
    def on_left_down(self, event):
        tool = self.current_tool.get()
        if tool == "no_collide_image":
            # 选中工具为“图像”，放置图像
            x = snap(self.canvas.canvasx(event.x), self.grid_cell)
            y = snap(self.canvas.canvasy(event.y), self.grid_cell)
            if self.selected_image in self.images.keys():
                tile = {"type": "no_collide_image", "x": x, "y": y,"w": 32.0, "h": 32.0, "path": self.selected_image}
                self.map['tiles'].append(tile)
                self.draw_tile_on_canvas(tile)
            else:
                messagebox.showwarning("提示", "你还没有选择任何图像")

        elif tool == "collide_image":
            # 选中工具为“图像”，放置图像
            x = snap(self.canvas.canvasx(event.x), self.grid_cell)
            y = snap(self.canvas.canvasy(event.y), self.grid_cell)
            if self.selected_image in self.images.keys():
                tile = {"type": "collide_image", "x": x, "y": y,"w": 32.0, "h": 32.0, "path": self.selected_image}
                self.map['tiles'].append(tile)
                self.draw_tile_on_canvas(tile)
            else:
                messagebox.showwarning("提示", "你还没有选择任何图像")

        elif tool == "water":
            # 选中工具为“图像”，放置图像
            x = snap(self.canvas.canvasx(event.x), self.grid_cell)
            y = snap(self.canvas.canvasy(event.y), self.grid_cell)
            if self.selected_image in self.images.keys():
                tile = {"type": "water", "x": x, "y": y,"w": 32.0, "h": 32.0, "path": self.selected_image}
                self.map['tiles'].append(tile)
                self.draw_tile_on_canvas(tile)
            else:
                messagebox.showwarning('提示', "你还没有选择任何图像")

        elif tool == "solid":
            self.is_drawing = True
            self.drag_start = (snap(self.canvas.canvasx(event.x), self.grid_cell),
                               snap(self.canvas.canvasy(event.y), self.grid_cell))
            self.preview_rect = self.canvas.create_rectangle(*self.drag_start, *self.drag_start,
                                                             outline="#ff0", dash=(2, 2))
        elif tool == "player":
            x = snap(self.canvas.canvasx(event.x), self.grid_cell)
            y = snap(self.canvas.canvasy(event.y), self.grid_cell)
            tile = {"type": tool, "x": x, "y": y, "args":{"healthy":100, "speed":230}}
            self.map['tiles'].append(tile)
            self.draw_tile_on_canvas(tile)

        elif tool == "enemy":
            x = snap(self.canvas.canvasx(event.x), self.grid_cell)
            y = snap(self.canvas.canvasy(event.y), self.grid_cell)
            tile = {"type": tool, "x": x, "y": y, "args":{"healthy":5, "speed":130}}
            self.map['tiles'].append(tile)
            self.draw_tile_on_canvas(tile)

        elif tool == "boss":
            x = snap(self.canvas.canvasx(event.x), self.grid_cell)
            y = snap(self.canvas.canvasy(event.y), self.grid_cell)
            tile = {"type": tool, "x": x, "y": y, "args":{"healthy":500, "speed":230}}
            self.map['tiles'].append(tile)
            self.draw_tile_on_canvas(tile)

        elif tool == "door":
            x = snap(self.canvas.canvasx(event.x), self.grid_cell)
            y = snap(self.canvas.canvasy(event.y), self.grid_cell)
            tile = {"type": tool, "x": x, "y": y, "args":{"target":"level2.json"}}
            self.map['tiles'].append(tile)
            self.draw_tile_on_canvas(tile)

        elif tool == "item":
            x = snap(self.canvas.canvasx(event.x), self.grid_cell)
            y = snap(self.canvas.canvasy(event.y), self.grid_cell)
            tile = {"type": tool, "x": x, "y": y}
            self.map['tiles'].append(tile)
            self.draw_tile_on_canvas(tile)

        elif tool == "select":
            self.select_at(event)

    def on_left_drag(self, event):
        if self.is_drawing and self.preview_rect:
            x1, y1 = self.drag_start
            x2 = snap(self.canvas.canvasx(event.x), self.grid_cell) + self.grid_cell
            y2 = snap(self.canvas.canvasy(event.y), self.grid_cell) + self.grid_cell
            self.canvas.coords(self.preview_rect, x1, y1, x2, y2)

    def on_left_up(self, event):
        if self.is_drawing and self.preview_rect:
            x1, y1 = self.drag_start
            x2 = snap(self.canvas.canvasx(event.x), self.grid_cell) + self.grid_cell
            y2 = snap(self.canvas.canvasy(event.y), self.grid_cell) + self.grid_cell
            tile = {"type": "solid", "x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1}
            self.map['tiles'].append(tile)
            self.canvas.delete(self.preview_rect)
            self.preview_rect = None
            self.draw_tile_on_canvas(tile)
        self.is_drawing = False

    def on_right_down(self, event):
        #获取鼠标在画布上的位置
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        self.n -= 1

        for t in list(self.map['tiles']):
            cid = t.get('_canvas_id')
            if cid and self.canvas.type(cid) == "rectangle":
                coords = self.canvas.coords(cid)
                if coords[0] <= x <= coords[2] and coords[1] <= y <= coords[3]:
                    self.canvas.delete(cid)
                    self.map['tiles'].remove(t)
                    break
            elif cid and self.canvas.type(cid) == "oval":
                coords = self.canvas.coords(cid)
                if coords[0] <= x <= coords[2] and coords[1] <= y <= coords[3]:
                    self.canvas.delete(cid)
                    self.map['tiles'].remove(t)
                    break

            #右键去除图像
            elif cid :   
                    cx, cy = self.canvas.coords(cid)
                    if cx <= x <= cx+self.grid_cell and cy <= y <= cy+self.grid_cell:
                        self.canvas.delete(cid)
                        self.map['tiles'].remove(t)
                        break

    def select_at(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        for t in self.map['tiles']:
            cid = t.get('_canvas_id')
            if cid and self.canvas.type(cid) == "rectangle":
                coords = self.canvas.coords(cid)
                if coords[0] <= x <= coords[2] and coords[1] <= y <= coords[3]:
                    dlg = PropertyDialog(self, "编辑属性", t)
                    if dlg.result:
                        for k, v in dlg.fields.items():
                            t[k] = v
                    break
            elif cid and self.canvas.type(cid) == "oval":
                coords = self.canvas.coords(cid)
                if coords[0] <= x <= coords[2] and coords[1] <= y <= coords[3]:
                    dlg = PropertyDialog(self, "编辑属性", t)
                    if dlg.result:
                        for k, v in dlg.fields.items():
                            t[k] = v
                    break
            #右键去除图像
            elif cid :
                cx, cy = self.canvas.coords(cid)
                if cx <= x <= cx+self.grid_cell and cy <= y <= cy+self.grid_cell:
                    dlg = PropertyDialog(self, "编辑属性", t)
                    if dlg.result:
                        for k, v in dlg.fields.items():
                            t[k] = v
                    break

    def on_delete(self, event):
        if self.selected_item:
            tile, cid = self.selected_item
            if cid:
                self.canvas.delete(cid)
            if tile in self.map['tiles']:
                self.map['tiles'].remove(tile)
            self.selected_item = None

    #json png操作
    def export_json(self):
        self.map['name'] = self.name_var.get()
        tiles = []
        entities = []
        for item in self.map['tiles']:
            if item['type'] in ('solid', 'no_collide_image',"collide_image","water"):
                tiles.append(item)
        for item in self.map['entities']:
                entities.append(item)

        map_data = {}
        map_data['name'] = self.map['name']
        map_data['width'] = self.map['width']
        map_data['height'] = self.map['height']
        map_data['tiles'] = tiles
        map_data['entities'] = entities

        f = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON 文件", "*.json")])
        if not f:
            return
        with open(f, "w", encoding="utf-8") as fp:
            json.dump(map_data, fp, ensure_ascii=False, indent=2)
        messagebox.showinfo("成功", "地图已导出为 JSON。")

    def export_png(self):
        f = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG 图片", "*.png")])
        if not f:
            return
        img = Image.new("RGB", (self.map['width'], self.map['height']), (34, 34, 34))
        draw = ImageDraw.Draw(img)
        for t in self.map['tiles']:
            if t['type'] == "solid":
                draw.rectangle([t['x'], t['y'], t['x'] + t['w'], t['y'] + t['h']], fill=(119, 119, 119))
            else:
                r = max(4, self.grid_cell // 3)
                color_map = {'enemy': (217, 83, 79), 'item': (91, 192, 222),
                             'door': (240, 173, 78), 'boss': (92, 184, 92)}
                color = color_map.get(t['type'], (255, 255, 255))
                draw.ellipse([t['x'] - r, t['y'] - r, t['x'] + r, t['y'] + r], fill=color)
        img.save(f)
        messagebox.showinfo("成功", "地图预览已导出为 PNG。")

    def load_json(self):
        f = filedialog.askopenfilename(filetypes=[("JSON 文件", "*.json")]) 
        if not f:
            return
        with open(f, "r", encoding="utf-8") as fp:
            self.map = json.load(fp)
        self.width_var.set(self.map['width'])
        self.height_var.set(self.map['height'])
        self.grid_var.set(self.grid_cell)
        
        # 自动加载所有图片资源
        for t in self.map['tiles']:
            if t['type'] in ("no_collide_image", "collide_image", "water"):
                img_path = t.get('path')
                if img_path and img_path not in self.images:
                    try:
                        img = Image.open(img_path) 
                        img = img.convert("RGBA")
                        img.thumbnail((self.grid_cell, self.grid_cell))
                        img_tk = ImageTk.PhotoImage(img)
                        self.images[img_path] = img_tk
                    except Exception as e:
                        messagebox.showwarning("图片加载失败", f"无法加载图片: {img_path}\n{e}")
 
        # 同步图片路径到下拉框
        self.image_combobox['values'] = list(self.images.keys())
        if self.images:
            self.selected_image = list(self.images.keys())[0]
            self.selected_image_preview_obj = self.images[self.selected_image]
            self.image_preview_lb.configure(image=self.selected_image_preview_obj)

        self.map['tiles'].extend(self.map['entities']) #extend()给定列表元素加到列表
        self.canvas.delete("all")  # 清空画布
        self.draw_grid()
       
        messagebox.showinfo("成功", "地图和实体已加载。")

if __name__ == "__main__":
    app = LevelEditor()
    app.mainloop()
