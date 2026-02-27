# pygame_pixel_platformer.py
# -*- coding: utf-8 -*-
"""
2D像素平台游戏(Pygame)模块化起步工程
=================================================

核心特性（满足你的需求）：
- 关卡解析:可解析你给的JSON格式 含 tiles + entities。
- 世界/相机：关卡不局限于屏幕，摄像机随玩家移动滚动。
- 实体系统：玩家、敌人（多行为：巡逻/跳跃/游走)、Boss、门、告示牌、掉落物/道具、方块/障碍、投射物（火球）。
- 物理/移动:A/D左右移动、跳跃与二段跳、S蹲下潜行、重力、在水中具有浮力与阻尼、速度变化、碰撞分离。
- 战斗与交互:玩家与Boss可发射火球,敌人/玩家受伤、Boss专属血条、吃道具获得能力(例如二段跳、冲刺、钥匙等)。
- 计时器与事件：通用 Timer 管理buff/冷却/闪烁等。
- UI:主菜单/暂停菜单、HUD(生命/能力图标/提示)、过关/胜利/失败面板。
- 资源占位：严格不使用 pygame.Rect 作为实体的几何；实现自定义 AABB。图像路径留空也可运行——将会使用纯色占位贴图;待你替换为像素图即可。

运行提示：
- 安装 pygame: `pip install pygame`
- 目录建议：
  project/
    pygame_pixel_platformer.py (本文件)
    assets/  (你的图片放这里；随意子文件夹)
    levels/
      level1.json
      level2.json
      ...
- 运行：`python pygame_pixel_platformer.py`，默认从 levels/level1.json 开始。
- 控制:A/D 移动,Space 跳跃,S 蹲下/潜行,k 发射火,E 交互(读告示牌/进门),Esc 打开暂停菜单 .


JSON格式(兼容你提供的示例):
{
    "name": "Level 1",
    "width": 800,
    "height": 600,
    "tiles": [
        {"type":"solid","x":0,"y":580,"w":800,"h":20,"path":"none"}
    ],
    "entities": [
        {"type":"player","x":100,"y":500,"args":{"health":100,"speed":5}},
        {"type":"enemy","x":400,"y":500,"args":{"variant":"patroller","health":50,"speed":3}},
        {"type":"door","x":760,"y":520,"args":{"target":"levels/level2.json"}},
        {"type":"sign","x":200,"y":540,"args":{"text":"按E交互: J发射火球"}}
    ]
}

Tiles 支持的 type: olid(实心)、oneway(单向平台)、water(水面/水域)、hazard(伤害，例如尖刺)、ice(低摩擦)、conveyor_left/right(传送带)。
Entities 支持: player, enemy(variant: patroller/jumper/wanderer), boss, door(target), sign(text), item(kind: double_jump/speed/fireball/key/health)、block(静态碰撞块)。

你可以自由扩展映射(见 LevelFactory)
"""
from __future__ import annotations
import os
import sys
import json
import math
import random
from typing import Dict, List, Tuple, Optional, Any, Callable

import pygame

# ------------------------------------------------------------
# 全局配置
# ------------------------------------------------------------
SCREEN_W, SCREEN_H = 960, 540
CAPTION = "Pixel Platformer Starter"
FPS = 60

# 物理常量
GRAVITY = 1600.0  # px/s^2
WATER_BUOYANCY = -900.0
WATER_DRAG = 0.6
AIR_DRAG = 0.02
GROUND_DRAG = 8.0
JUMP_VELOCITY = -600.0
DOUBLE_JUMP_VELOCITY = -570.0
MAX_FALL_SPEED = 1200.0

# 颜色（占位渲染用）
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (220, 50, 50)
GREEN = (50, 200, 120)
BLUE = (80, 120, 255)
YELLOW = (240, 220, 70)
ORANGE = (255, 160, 60)
PURPLE = (170, 120, 255)
CYAN = (100, 220, 220)
GRAY = (150, 150, 150)

# 资源占位尺寸
TILE_SIZE = 32
ENTITY_SIZE = 32
PROJECTILE_SIZE = 10

#图像路径
PLAYER_IMAGE_PATH = 'assets/magician.png' 
MONSTER_1_IMAGE_PATH = 'assets/Monster_1.png'
MONSTER_2_IMAGE_PATH = 'assets/Monster_2.png'
ATTENTION_IMAGE_PATH = 'assets/attention.png'
DOOR_IMAGE_PATH = 'assets/door.png'
WATER_IMAGE_PATH = 'assets/water-surface.png'
FOOD_IMAGE_PATH = 'assets/coin.png'
SPIKES_IMAGE_PATH = 'assets/spikes.png'


#地图编辑器提供的关卡json           根目录              相对目录
LEVEL_ROOT = os.path.join(os.path.dirname(__file__), "../levels")


# 通用工具
# ------------------------------------------------------------
class AABB:
    """自定义 Axis-Aligned Bounding Box,不使用 pygame.Rect。"""
    __slots__ = ("x", "y", "w", "h")
    def __init__(self, x: float, y: float, w: float, h: float):
        self.x, self.y, self.w, self.h = x, y, w, h
    @property
    def left(self): return self.x  
    @property
    def right(self): return self.x + self.w
    @property
    def top(self): return self.y
    @property
    def bottom(self): return self.y + self.h
    def copy(self):
        return AABB(self.x, self.y, self.w, self.h)
    def move(self, dx: float, dy: float):
        self.x += dx; self.y += dy
    def set_pos(self, x: float, y: float):
        self.x, self.y = x, y
    def intersects(self, other: "AABB") -> bool:
        return not (self.right <= other.left or self.left >= other.right or self.bottom <= other.top or self.top >= other.bottom)
    def intersection(self, other: "AABB") -> Tuple[float, float]:
        if not self.intersects(other):
            return (0.0, 0.0)
        dx1 = other.right - self.left
        dx2 = self.right - other.left
        dy1 = other.bottom - self.top
        dy2 = self.bottom - other.top
        # 取最小分离向量
        sx = dx1 if dx1 < dx2 else -dx2
        sy = dy1 if dy1 < dy2 else -dy2
        if abs(sx) < abs(sy):
            return (sx, 0.0)
        else:
            return (0.0, sy)

# 简易计时器
class Timer:
    def __init__(self):
        self.events: List[Tuple[float, Callable]] = []
    def add(self, delay_sec: float, cb: Callable):
        self.events.append([delay_sec, cb])
    def update(self, dt: float):
        for e in list(self.events):
            e[0] -= dt
            if e[0] <= 0:
                try:
                    e[1]()
                finally:
                    self.events.remove(e)

# 资源加载（允许 path=="none" 或空）
class AssetLoader:
    _cache: Dict[str, pygame.Surface] = {}
    @staticmethod
    def load_image(path: Optional[str], size: Tuple[int, int], color=(200, 200, 200)) -> pygame.Surface:
        key = f"{path}|{size}|{color}"
        if key in AssetLoader._cache:
            return AssetLoader._cache[key]
        surf = pygame.Surface(size, flags=pygame.SRCALPHA)
        if path and path.lower() != "none" and os.path.isfile(path):
            try:
                img = pygame.image.load(path).convert_alpha()
                surf = pygame.transform.smoothscale(img, size)
            except Exception:
                surf.fill(color)
        else:
            surf.fill(color)  # 占位
            # 画一个十字提示待替换
            pygame.draw.line(surf, (50, 50, 50), (0, 0), (size[0], size[1]), 2)
            pygame.draw.line(surf, (50, 50, 50), (size[0], 0), (0, size[1]), 2)
        AssetLoader._cache[key] = surf
        return surf

#游戏背景
class Background:
    """游戏背景类，支持多层背景滚动效果"""
    def __init__(self, image_paths: List[Optional[str]], scroll_ratios: List[float] = None):
        """
        初始化背景
        :param image_paths: 背景图像路径列表(从后到前)
        :param scroll_ratios: 各层滚动比例(与相机移动的比例),None则默认[0.1, 0.3, 0.6, 1.0]等
        """
        self.layers = []
        self.scroll_ratios = scroll_ratios or []
        
        # 加载背景图层
        for i, path in enumerate(image_paths):
            # 对于没有指定路径的图层，使用纯色背景
            if not path or path.lower() == "none":
                surf = pygame.Surface((SCREEN_W, SCREEN_H))
                # 每层使用略微不同的深色作为默认
                color = (10 + i*15, 15 + i*15, 30 + i*15)
                surf.fill(color)
                self.layers.append(surf)
            else:
                try:
                    img = pygame.image.load(path).convert_alpha()
                    # 缩放图像以适应屏幕
                    surf = pygame.transform.scale(img, (SCREEN_W, SCREEN_H))
                    self.layers.append(surf)
                except Exception as e:
                    print(f"加载背景图像 {path} 失败: {e}")
                    # 加载失败时使用备用颜色
                    surf = pygame.Surface((SCREEN_W, SCREEN_H))
                    surf.fill((30, 30, 50))
                    self.layers.append(surf)
        
        # 初始化滚动比例（如果未指定）
        if not self.scroll_ratios:
            num_layers = len(self.layers)
            self.scroll_ratios = [(i + 1) / (num_layers * 2) for i in range(num_layers)]

    def draw(self, surf: pygame.Surface, camera: Camera):
        """绘制背景，根据相机位置计算各层偏移"""
        for i, layer in enumerate(self.layers):
            # 计算该层的滚动偏移（与相机移动成比例）
            ratio = self.scroll_ratios[i]
            offset_x = camera.x * ratio
            offset_y = camera.y * ratio
            surf.blit(layer, (offset_x, offset_y))
            # # 处理图像平铺（如果需要重复背景）
            # # 计算需要绘制的次数以覆盖屏幕
            # x = -offset_x % layer.get_width()
            # while x < SCREEN_W:
            #     y = -offset_y % layer.get_height()
            #     while y < SCREEN_H:
            #         surf.blit(layer, (x, y))
            #         y += layer.get_height()
            #     x += layer.get_width()


# 世界与关卡
# ------------------------------------------------------------
class Tile:
    def __init__(self, kind: str, aabb: AABB, image: Optional[pygame.Surface]=None):
        self.kind = kind
        self.aabb = aabb
        self.image = image

class SpatialHash:
    """简单空间哈希加速碰撞查询。"""
    def __init__(self, cell: int = 64):
        self.cell = cell
        self.grid: Dict[Tuple[int,int], List[Any]] = {}

    def _key(self, x: float, y: float) -> Tuple[int,int]:
        return (int(x)//self.cell, int(y)//self.cell)
    
    def insert(self, aabb: AABB, obj: Any):
        minx, miny = self._key(aabb.left, aabb.top)
        maxx, maxy = self._key(aabb.right, aabb.bottom)
        for gx in range(minx, maxx+1):
            for gy in range(miny, maxy+1):
                self.grid.setdefault((gx,gy), []).append(obj)

    def query(self, aabb: AABB) -> List[Any]:
        res = []
        minx, miny = self._key(aabb.left, aabb.top)
        maxx, maxy = self._key(aabb.right, aabb.bottom)
        for gx in range(minx, maxx+1):
            for gy in range(miny, maxy+1):
                res.extend(self.grid.get((gx,gy), []))
        return res
    
    def clear(self):
        self.grid.clear()

class Level:
    def __init__(self, data: Dict[str, Any]):
        self.name = data.get("name", "Unnamed")
        self.world_w = int(data.get("width", SCREEN_W))
        self.world_h = int(data.get("height", SCREEN_H))
        self.tiles: List[Tile] = []
        self.entities: List[Entity] = []  # type: ignore  # forward
        self.spatial = SpatialHash(64)
        self.player: Optional[Player] = None  # type: ignore
        self.boss: Optional[Boss] = None  # type: ignore
        self.doors: List[Door] = []  # type: ignore

        #-------------------------------------------------------
        #背景支持
        self.background = None
        # bg_data = data.get("background", {})
        # if bg_data:
        #     for b in bg_data:

        #         image_paths = b.get("layers", [])
        #         scroll_ratios = b.get("scroll_ratios", None)
        #         self.background = Background(image_paths, scroll_ratios)
        #-------------------------------------------------------

        # 解析 tiles   如果是tile将载入相关路径
        for t in data.get("tiles", []):
            aabb = AABB(float(t["x"]), float(t["y"]), float(t["w"]), float(t["h"]))
            kind = t.get("type", "solid")
            path = t.get("path")
            img = AssetLoader.load_image(path if path else None, (int(aabb.w), int(aabb.h)), color=GRAY)
            self.tiles.append(Tile(kind, aabb, img))
        # 解析 entities
        for e in data.get("entities", []):
            ent = LevelFactory.create_entity(e["type"], float(e.get("x",0)), float(e.get("y",0)), e.get("args",{}))
            if ent:
                self.entities.append(ent)
                if isinstance(ent, Player):
                    self.player = ent
                if isinstance(ent, Boss):
                    self.boss = ent
                if isinstance(ent, Door):
                    self.doors.append(ent)

    def build_spatial(self):
        self.spatial.clear()
        for t in self.tiles:
            self.spatial.insert(t.aabb, t)


# 实体与组件
# ------------------------------------------------------------
class Entity:
    def __init__(self, x: float, y: float, w: int=ENTITY_SIZE, h: int=ENTITY_SIZE, sprite_path: Optional[str]=None, color=WHITE):
        self.aabb = AABB(x, y, w, h)
        self.vx = 0.0
        self.vy = 0.0
        self.on_ground = False
        self.in_water = False
        self.remove_requested = False
        self.health = 1
        self.max_health = 1
        self.facing = 1
        self.sprite = AssetLoader.load_image(sprite_path, (w, h), color=color)
        self.shadow = None

    def update(self, dt: float, game: "Game"):
        pass

    def draw(self, surf: pygame.Surface, camera: "Camera"):
        x = int(self.aabb.x - camera.x)
        y = int(self.aabb.y - camera.y)

        img = self.sprite
        # 根据方向翻转图像
        if self.facing == -1:
            img = pygame.transform.flip(self.sprite, True, False)
        if self.shadow:
            surf.blit(self.shadow, (x, y))
        surf.blit(img, (x, y))
        
    def hurt(self, dmg: int, knockback: Tuple[float,float]=(0,0)):
        self.health = max(0, self.health - dmg)
        self.vx += knockback[0]
        self.vy += knockback[1]
        if self.health <= 0:
            self.remove_requested = True

class Projectile(Entity):
    #dmg为火球伤害
    #处理火球逻辑
    def __init__(self, x, y, dir, speed=500, dmg=40, owner: Optional[Entity]=None, sprite_path=None, color=ORANGE):
        super().__init__(x, y, PROJECTILE_SIZE, PROJECTILE_SIZE, sprite_path, color)
        self.vx = speed * dir
        self.vy = 0
        self.owner = owner
        self.damage = dmg
        self.ttl = 3.0
    def update(self, dt, game: "Game"):
        self.ttl -= dt
        if self.ttl <= 0:
            self.remove_requested = True
            return
        # 移动
        self.aabb.move(self.vx*dt, self.vy*dt)
        # 撞到固体tile就销毁
        for t in game.level.spatial.query(self.aabb):
            if isinstance(t, Tile) and t.kind in ("solid","oneway","ice","image","conveyor_left","conveyor_right"):
                if self.aabb.intersects(t.aabb):
                    self.remove_requested = True
                    return
        # 碰撞生物
        targets = []
        if isinstance(self.owner, Player):
            targets = [e for e in game.level.entities if isinstance(e, (Enemy, Boss))]
        else:
            targets = [e for e in game.level.entities if isinstance(e, Player)]
        for e in targets:
            if e is not self.owner and self.aabb.intersects(e.aabb):
                e.hurt(self.damage, (self.vx*0.02, -150))
                self.remove_requested = True
                break

class Creature(Entity):
    #物理引擎
    def __init__(self, x, y, w, h, sprite_path=None, color=WHITE):
        super().__init__(x, y, w, h, sprite_path, color)
        self.acc = 2000.0
        self.max_speed = 220.0
        self.jump_power = JUMP_VELOCITY
        self.double_jump_power = DOUBLE_JUMP_VELOCITY
        self.can_double_jump = False
        self.has_key = False
        self.fire_cooldown = 0.0
        self.move_intent = 0.0
        self.want_jump = False
        self.want_shoot = False
        self.crouching = False
        self.last_damage_time = 0  # 上次受到伤害的时间
        self.damage_cooldown = 1.0  # 伤害冷却时间（秒），防止连续扣血

    def physics(self, dt: float, game: "Game"):
        # 水/空气阻力
        drag = WATER_DRAG if self.in_water else (GROUND_DRAG if self.on_ground else AIR_DRAG)
        self.vx -= self.vx * drag * dt
        # 加速度
        self.vx += self.move_intent * self.acc * dt
        self.vx = max(-self.max_speed, min(self.max_speed, self.vx))
        # 重力/浮力
        if self.in_water:
            self.vy += WATER_BUOYANCY * dt
        else:
            self.vy += GRAVITY * dt
        self.vy = max(-2000, min(MAX_FALL_SPEED, self.vy))

        # 跳跃
        if self.want_jump:
            if self.on_ground or (self.in_water):
                self.vy = self.jump_power
                self.on_ground = False
            elif self.can_double_jump:
                self.vy = self.double_jump_power
                self.can_double_jump = False
            self.want_jump = False

        # 位移与碰撞分离（按轴）
        self._move_and_collide(dt, game)

    def _move_and_collide(self, dt: float, game: "Game"):
        # X轴
        self.aabb.move(self.vx*dt, 0)
        self.aabb.x = max(0, min(self.aabb.x, game.level.world_w - self.aabb.w))
        collided_x = False
        for t in game.level.spatial.query(self.aabb):
            if not isinstance(t, Tile):
                continue
            if t.kind in ("solid","ice","collide_image","conveyor_left","conveyor_right") and self.aabb.intersects(t.aabb):
                sx, sy = self.aabb.intersection(t.aabb)
                if sx != 0:
                    self.aabb.move(sx, 0)
                    self.vx = 0
                    collided_x = True
        # Y轴
        self.aabb.move(0, self.vy*dt)
        self.on_ground = False
        self.in_water = False
        for t in game.level.spatial.query(self.aabb):
            if not isinstance(t, Tile):
                continue
            if t.kind == "water" and self.aabb.intersects(t.aabb):
                self.in_water = True
            if t.kind in ("solid","ice","collide_image") and self.aabb.intersects(t.aabb):
                sx, sy = self.aabb.intersection(t.aabb)
                if sy != 0:
                    self.aabb.move(0, sy)
                    if sy < 0:  # 脚踩在地
                        self.on_ground = True
                        self.can_double_jump = True  # 落地重置二段跳
                    self.vy = 0
            if t.kind == "oneway":
                # 仅从上方站立
                if self.vy >= 0 and self.aabb.bottom > t.aabb.top and self.aabb.top < t.aabb.top and abs(self.aabb.right - t.aabb.left) > 1 and abs(self.aabb.left - t.aabb.right) > 1:
                    if self.aabb.bottom > t.aabb.top and self.aabb.intersects(t.aabb):
                        self.aabb.set_pos(self.aabb.x, t.aabb.top - self.aabb.h)
                        self.on_ground = True
                        self.can_double_jump = True
                        self.vy = 0
            if t.kind == "hazard" and self.aabb.intersects(t.aabb):
                self.hurt(10, (0, -200))
            if t.kind == "conveyor_left" and self.on_ground:
                self.aabb.move(-40*dt, 0)
            if t.kind == "conveyor_right" and self.on_ground:
                self.aabb.move(40*dt, 0)


# ------------------------------------------------------------
class Player(Creature):
    def __init__(self, x, y, args: Dict[str, Any]):
        super().__init__(x, y, ENTITY_SIZE, ENTITY_SIZE, PLAYER_IMAGE_PATH, color=BLUE)
        self.max_health = int(args.get("health", 100))
        self.health = self.max_health
        self.max_speed = float(args.get("speed", 220))
        self.acc = 2200.0
        self.jump_power = JUMP_VELOCITY
        self.double_jump_power = DOUBLE_JUMP_VELOCITY
        self.unlocked_fireball = True  # 可以通过道具锁/解
        self.inventory: Dict[str, int] = {}
        self.iframes = 0.0

    def handle_input(self, keys: pygame.key.ScancodeWrapper):
        self.move_intent = 0.0
        moved = False
        if keys[pygame.K_a]:
            self.move_intent -= 1.0
            self.facing = -1
            moved = True
        if keys[pygame.K_d]:
            self.move_intent += 1.0
            self.facing = 1
            moved = True
        self.crouching = bool(keys[pygame.K_s])
        # # debug
        # if moved:
        #     print(f"[DEBUG] move_intent={self.move_intent} vx={self.vx}")

    def update(self, dt: float, game: "Game"):
        keys = pygame.key.get_pressed()
        self.handle_input(keys)
        # 跳跃按键沿用事件触发（防止长按多次）
        # 发射
        self.fire_cooldown = max(0.0, self.fire_cooldown - dt)
        self.iframes = max(0.0, self.iframes - dt)
        self.physics(dt, game)

        # 掉出屏幕判定为死亡
        if self.aabb.y > game.level.world_h:
            self.remove_requested = True
        # 拾取道具
        for e in list(game.level.entities):
            if isinstance(e, Item) and self.aabb.intersects(e.aabb):
                e.apply(self)
                e.remove_requested = True
        # 门 & 告示牌交互
        if keys[pygame.K_e]:
            for d in game.level.doors:
                if self.aabb.intersects(d.aabb):
                    game.load_level(d.target)
            for e in game.level.entities:
                if isinstance(e, Sign) and self.aabb.intersects(e.aabb):
                    game.hud.set_message(e.text)

    def on_jump_pressed(self):
        self.want_jump = True

    def on_shoot_pressed(self):
        if self.unlocked_fireball and self.fire_cooldown <= 0.0:
            p = Projectile(self.aabb.x + self.aabb.w/2, self.aabb.y + self.aabb.h/2, self.facing, speed=560, dmg=12, owner=self)
            self.fire_cooldown = 0.25
            return p
        return None

    def hurt(self, dmg: int, knockback=(0,0)):
        if self.iframes > 0:
            return
        super().hurt(dmg, knockback)
        self.iframes = 1.0

    def take_damage(self, amount, knockback: tuple[float, float], game: "Game"):
        """玩家受到伤害的处理方法"""
        current_time = pygame.time.get_ticks() / 1000.0  # 获取当前时间（秒）
        
        # 检查是否在冷却时间内
        if current_time - self.last_damage_time < self.damage_cooldown:
            return
            
        # 扣血
        self.health -= amount
        self.last_damage_time = current_time
        
        # 应用击退效果
        self.vx, self.vy = knockback
        
        # 检查是否死亡
        if self.health <= 0:
            self.remove_requested = True

class Enemy(Creature):
    def __init__(self, x, y, args: Dict[str, Any]):
        color = RED
        super().__init__(x, y, 35, 40, MONSTER_1_IMAGE_PATH, color=color)
        self.variant = args.get("variant", "patroller")
        self.max_health = int(args.get("health", 40))
        self.health = self.max_health
        self.max_speed = float(args.get("speed", 180))
        self.jump_timer = random.uniform(1.0, 2.5)

    def ai(self, dt: float, game: "Game"):
        # 简化AI：根据variant调整行为
        player = game.level.player
        self.move_intent = 0.0

        #三种怪物类型
        if self.variant == "patroller":
            # 循环左右巡逻
            if abs(self.vx) < 10:
                self.facing *= -1
            self.move_intent = self.facing
        elif self.variant == "jumper":
            self.jump_timer -= dt
            if self.jump_timer <= 0:
                self.want_jump = True
                self.jump_timer = random.uniform(1.2, 2.0)
            # 轻微朝玩家移动
            if player:
                self.move_intent = 1.0 if player.aabb.x > self.aabb.x else -1.0
                self.facing = 1 if self.move_intent > 0 else -1
        elif self.variant == "wanderer":
            # 随机游走
            self.move_intent = math.sin(pygame.time.get_ticks()*0.001 + id(self)%10)
            self.facing = 1 if self.move_intent >= 0 else -1



        #检测前方是否有地面 防止掉入悬崖
        check_distance = 10
        foot_x = self.aabb.x + (self.aabb.w if self.facing > 0 else -check_distance)
        foot_y = self.aabb.y + self.aabb.h + 2
        foot_aabb = AABB(foot_x, foot_y, check_distance, 4)
        has_ground = False
        for t in game.level.spatial.query(foot_aabb):
            if isinstance(t, Tile) and t.kind in ("solid", "water", "ice", "collide_image"):
                if foot_aabb.intersects(t.aabb):
                    has_ground = True
                    break
        if not has_ground:
            self.facing *= -1
            self.move_intent = self.facing


        # 简单远程：偶尔射击
        if player and random.random() < 0.004:
            if abs(player.aabb.x - self.aabb.x) < 400 and abs(player.aabb.y - self.aabb.y) < 100:
                dir = 1 if player.aabb.x > self.aabb.x else -1
                return Projectile(self.aabb.x+self.aabb.w/2, self.aabb.y+self.aabb.h/2, dir, speed=420, dmg=8, owner=self, color=PURPLE)
        return None

    def update(self, dt: float, game: "Game"):
         # 检测与玩家的碰撞
        self.check_player_collision(game)

        proj = self.ai(dt, game)
        if proj:
            game.spawn(proj)
        self.physics(dt, game)

    def check_player_collision(self, game: "Game"):
        """检测是否与玩家碰撞，如果碰撞则让玩家扣血"""
        if game.level.player and self.aabb.intersects(game.level.player.aabb):
            # 计算击退方向（从怪物指向玩家）
            knockback_x = 300 if game.level.player.aabb.x > self.aabb.x else -300
            knockback = (knockback_x, -200)  # 向上击退，模拟被打飞效果
            
            # 玩家扣血（怪物基础伤害10点）
            game.level.player.take_damage(10, knockback, game)

class Boss(Creature):
    def __init__(self, x, y, args: Dict[str, Any]):
        super().__init__(x, y, ENTITY_SIZE*2, ENTITY_SIZE*2, args.get("sprite"), color=YELLOW)
        self.max_health = int(args.get("health", 300))
        self.health = self.max_health
        self.max_speed = float(args.get("speed", 180))
        self.pattern_t = 0.0
        self.phase = 1
        self.fire_cd = 0.0

    def update(self, dt: float, game: "Game"):
        player = game.level.player
        if player:
            self.move_intent = 1.0 if player.aabb.x > self.aabb.x else -1.0
            self.facing = 1 if self.move_intent > 0 else -1
        # 阶段与射击模式
        self.pattern_t += dt
        self.fire_cd = max(0.0, self.fire_cd - dt)
        if self.fire_cd == 0.0 and player:
            # 发射扇形火球
            for ang in (-0.3, -0.15, 0, 0.15, 0.3):
                dir = 1 if player.aabb.x > self.aabb.x else -1
                p = Projectile(self.aabb.x+self.aabb.w/2, self.aabb.y+self.aabb.h/2, dir, speed=520, dmg=10, owner=self, color=ORANGE)
                # 在水平速度基础上加一点角速度
                p.vy = math.tan(ang) * abs(p.vx)
                game.spawn(p)
            self.fire_cd = 1.2 if self.phase==1 else 0.8
        # 血量驱动阶段
        hp_ratio = self.health / self.max_health
        self.phase = 2 if hp_ratio < 0.5 else 1
        if self.phase == 2:
            self.max_speed = 240
            self.acc = 2600
        self.physics(dt, game)

        # 检测与玩家的碰撞
        self.check_player_collision(game)

    def check_player_collision(self, game: "Game"): 
        """BOSS与玩家碰撞的处理(伤害更高)"""
        if game.level.player and self.aabb.intersects(game.level.player.aabb):
            # BOSS的击退更强
            knockback_x = 400 if game.level.player.aabb.centerx > self.aabb.centerx else -400
            knockback = (knockback_x, -300)
            
            # BOSS伤害更高（20点）
            game.level.player.take_damage(20, knockback, game)

class Item(Entity):
    def __init__(self, x, y, args: Dict[str, Any]):
        kind = args.get("kind", "health")
        color = CYAN if kind != "health" else GREEN
        super().__init__(x, y, TILE_SIZE, TILE_SIZE, FOOD_IMAGE_PATH, color=color)
        self.kind = kind
        self.amount = int(args.get("amount", 25))
    def apply(self, player: Player):
        if self.kind == "health":
            player.health = min(player.max_health, player.health + self.amount)
        elif self.kind == "double_jump":
            player.can_double_jump = True
        elif self.kind == "speed":
            player.max_speed += 40
        elif self.kind == "fireball":
            player.unlocked_fireball = True
        elif self.kind == "key":
            player.has_key = True

class Door(Entity):
    def __init__(self, x, y, args: Dict[str, Any]):
        super().__init__(x, y, 50, TILE_SIZE*3, DOOR_IMAGE_PATH, color=GRAY)
        self.target = args.get("target", None)
        self.is_enter = False


    def handle_output():
        pass

    def update(self, dt, game):
        if self.aabb.intersects(game.level.player.aabb):
            self.is_enter = True
        return super().update(dt, game)           #返回到父类的update()
        
class Sign(Entity):
    def __init__(self, x, y, args: Dict[str, Any]):
        super().__init__(x, y, TILE_SIZE, TILE_SIZE, ATTENTION_IMAGE_PATH, color=WHITE)
        self.text = args.get("text", "")

class Block(Entity):
    def __init__(self, x, y, args: Dict[str, Any]):
        super().__init__(x, y, int(args.get("w", TILE_SIZE)), int(args.get("h", TILE_SIZE)), SPIKES_IMAGE_PATH, color=GRAY)


# 工厂
# -----------------------------------------------------------
class LevelFactory:
    @staticmethod
    def create_entity(kind: str, x: float, y: float, args: Dict[str, Any]) -> Optional[Entity]:
        kind = (kind or "").lower()
        if kind == "player":
            return Player(x, y, args)
        if kind == "enemy":
            return Enemy(x, y, args)
        if kind == "boss":
            return Boss(x, y, args)
        if kind == "item":
            return Item(x, y, args)
        if kind == "door":
            return Door(x, y, args)
        if kind == "sign":
            return Sign(x, y, args)
        if kind == "block":
            return Block(x, y, args)
        return None



# 摄像机 & HUD & 菜单
# ------------------------------------------------------------
class Camera:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
    def update(self, target: Entity, level: Level):
        # 平滑跟随
        tx = target.aabb.x + target.aabb.w/2 - SCREEN_W/2
        ty = target.aabb.y + target.aabb.h/2 - SCREEN_H/2
        self.x += (tx - self.x) * 0.12
        self.y += (ty - self.y) * 0.12
        # 限制在关卡内
        self.x = max(0, min(self.x, level.world_w - SCREEN_W))
        self.y = max(0, min(self.y, level.world_h - SCREEN_H))

class HUD:
    def __init__(self, game: "Game"):
        self.game = game
        self.font = pygame.font.SysFont("SimHei", 18)
        self.big = pygame.font.SysFont("SimHei", 32)
        self.message = ""
        self.msg_timer = 0.0

    def set_message(self, text: str, t: float=3.0):
        self.message = text
        self.msg_timer = t

    def update(self, dt: float):
        self.msg_timer = max(0.0, self.msg_timer - dt)

    def draw(self, surf: pygame.Surface):
        # 玩家血条
        p = self.game.level.player
        if p:
            ratio = p.health / max(1, p.max_health)
            pygame.draw.rect(surf, BLACK, (20, 20, 220, 22), 0)
            pygame.draw.rect(surf, RED, (22, 22, int(216*ratio), 18), 0)
            txt = self.font.render(f"HP {p.health}/{p.max_health}", True, WHITE)
            surf.blit(txt, (24, 22))
        # Boss 血条
        b = self.game.level.boss
        if b:
            ratio = b.health / max(1, b.max_health)
            pygame.draw.rect(surf, BLACK, (SCREEN_W//2-200, 20, 400, 16), 0)
            pygame.draw.rect(surf, ORANGE, (SCREEN_W//2-198, 22, int(396*ratio), 12), 0)
        # 提示
        if self.msg_timer > 0 and self.message:
            msg = self.big.render(self.message, True, YELLOW)
            surf.blit(msg, (SCREEN_W//2 - msg.get_width()//2, 60))

# 简单菜单
class Menu:
    def __init__(self):
        self.font = pygame.font.SysFont("SimHei", 28)
        self.small = pygame.font.SysFont("SimHei", 18)
        #Menu状态
        self.active = True
        self.describle = False
        self.paused = False
        self.items = ["开始游戏", "地图编辑器", "说明", "退出"]
        self.sel = 0

    def draw_centered(self, surf: pygame.Surface, title: str):
        font = pygame.font.SysFont("SimHei", 58)
        title_s = font.render(title, True, WHITE)
        surf.blit(title_s, (SCREEN_W//2 - title_s.get_width()//2, 110))
        for i, it in enumerate(self.items):
            t = self.font.render((" >" if i==self.sel else "  ")+it, True, WHITE if i==self.sel else GRAY)
            surf.blit(t, (SCREEN_W//2 - 100, 220 + i*40))
        hint = self.small.render("Enter确认  ↑↓选择  Esc返回/暂停", True, GRAY)
        surf.blit(hint, (SCREEN_W//2 - hint.get_width()//2, SCREEN_H-80))



# 游戏主类
# ------------------------------------------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(CAPTION)
        self.font = pygame.font.SysFont("SimHei",22)
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self.clock = pygame.time.Clock()
        self.camera = Camera()
        self.hud = HUD(self)
        self.menu = Menu()
        self.timer = Timer()
        self.running = True
        self.current_level_path = os.path.join(LEVEL_ROOT, "level1.json")
        self.level = self._load_or_default(self.current_level_path)
        self.projectiles: List[Projectile] = []

    def _load_or_default(self, path: str) -> Level:
        self.current_level_path = path
        if not os.path.isfile(path):
            # 构造一个默认关卡
            data = {
                "name": "Default",
                "width": 1600,
                "height": 900,
                "tiles": [
                    {"type":"solid","x":0,"y":860,"w":1600,"h":40,"path":"none"},
                    {"type":"solid","x":300,"y":760,"w":200,"h":20,"path":"none"},
                    {"type":"oneway","x":640,"y":660,"w":200,"h":12,"path":"none"},
                    {"type":"water","x":900,"y":820,"w":200,"h":40,"path":"none"},
                    {"type":"hazard","x":1200,"y":840,"w":160,"h":20,"path":"none"}
                ],
                "entities": [
                    {"type":"player","x":80,"y":780,"args":{"health":100,"speed":240}},
                    {"type":"enemy","x":500,"y":740,"args":{"variant":"patroller","health":50,"speed":180}},
                    {"type":"enemy","x":720,"y":620,"args":{"variant":"jumper","health":40,"speed":160}},
                    {"type":"item","x":350,"y":728,"args":{"kind":"double_jump"}},
                    {"type":"door","x":1550,"y":780,"args":{"target": os.path.join(LEVEL_ROOT, "level1.json")}},
                    {"type":"sign","x":200,"y":820,"args":{"text":"A/D移动 Space跳跃 S蹲下 J射击 E交互"}}
                ]
            }
            level = Level(data)
        else:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            level = Level(data)
        level.build_spatial()
        # 若没有玩家，创建一个
        if not level.player:
            p = Player(100, 100, {"health":100, "speed":240})
            level.entities.append(p)
            level.player = p
        return level

    def load_level(self, path: Optional[str]):
        if not path:
            return
        try:
            self.level = self._load_or_default(path)
            self.projectiles.clear()
            self.hud.set_message(f"进入 {self.level.name}")
        except Exception as e:
            self.hud.set_message(f"载入关卡失败: {e}")

    def spawn(self, ent: Entity):
        self.level.entities.append(ent)

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            if self.menu.active:
                self.draw_menu()
                continue
            if self.menu.paused:
                self.draw_pause()
                continue
            if self.menu.describle:
                self.draw_describle()
                continue
            self.update(dt)
            self.draw()
        pygame.quit()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.menu.active:
                        self.running = False
                    else:
                        self.menu.paused = not self.menu.paused
                if self.menu.active:
                    if event.key in (pygame.K_UP, pygame.K_w):
                        self.menu.sel = (self.menu.sel - 1) % len(self.menu.items)
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.menu.sel = (self.menu.sel + 1) % len(self.menu.items)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if self.menu.sel == 0:
                            self.menu.active = False

                        elif self.menu.sel == 1:
                            import subprocess, sys
                            subprocess.Popen([sys.executable, "-m", "editor.MapEditor_tk"])
                        elif self.menu.sel == 2:
                            self.menu.active = False
                            self.menu.describle =True
                        elif self.menu.sel == 3:
                            self.running = False
                elif event.key ==pygame.K_p:
                        self.menu.active = True
                        self.menu.describle = False
                else:
                    # 游戏中：输入
                    p = self.level.player
                    if not p:
                        continue
                    if event.key == pygame.K_SPACE:
                        p.on_jump_pressed()
                    if event.key == pygame.K_k:
                        proj = p.on_shoot_pressed()
                        if proj:
                            self.spawn(proj)
            elif event.type == pygame.VIDEORESIZE:
                pass

    def update(self, dt: float):
        self.timer.update(dt)
        self.level.build_spatial()  # 关卡静态物仍可动态重建以支撑可破坏地形（简单处理）
        # 更新实体
        for e in list(self.level.entities):
            e.update(dt, self)
            if e.remove_requested:
                self.level.entities.remove(e)
        # 更新投射物
        for p in list(self.projectiles):
            p.update(dt, self)
            if p.remove_requested:
                self.projectiles.remove(p)

        # 玩家是否进门
        for d in self.level.doors:
            if d.is_enter:
                target = d.target
                self.load_level(os.path.join(LEVEL_ROOT, target))
            else:
                target = "level1.json" #默认重新


        # Boss死亡 -> 胜利
        if self.level.boss and self.level.boss.remove_requested:
            self.hud.set_message("胜利！")
            self.timer.add(2.0, lambda: self.menu.__setattr__("active", True))
        # 玩家死亡 -> 失败/重来
        if self.level.player and self.level.player.remove_requested:
            self.hud.set_message("你失败了")
            self.timer.add(3.0, lambda: self.load_level(self.current_level_path))


        # 摄像机
        if self.level.player:
            self.camera.update(self.level.player, self.level)
        # HUD
        self.hud.update(dt)

    def draw_world(self, surf: pygame.Surface):
        # 先绘制背景(如果有)
        if self.level.background:
            self.level.background.draw(surf, self.camera)
        else:
            # 默认背景色
            surf.fill((20, 24, 28))
    
        cam = self.camera
        # 绘制 tile
        for t in self.level.tiles:
            # 视野裁剪
            if t.aabb.right < cam.x or t.aabb.left > cam.x+SCREEN_W or t.aabb.bottom < cam.y or t.aabb.top > cam.y+SCREEN_H:
                continue
            x = int(t.aabb.x - cam.x)
            y = int(t.aabb.y - cam.y)
            surf.blit(t.image, (x, y))
            if t.kind == "water":
                pygame.draw.rect(surf, BLUE, (x, y, t.aabb.w, 4))
        # 绘制实体
        for e in self.level.entities:
            e.draw(surf, cam)
        # 投射物
        for p in self.projectiles:
            p.draw(surf, cam)

    def draw(self):
        self.draw_world(self.screen)
        self.hud.draw(self.screen)

        # 文字
        font = pygame.font.SysFont("SimHei", 15)
        txt = font.render("A/D 移动,Space 跳跃,S 蹲下/潜行,k 发射火球,E 交互(告示牌/门),Esc 暂停菜单", True, WHITE)
        self.screen.blit(txt, (24,50))

        pygame.display.flip()

#GUI
    def draw_menu(self):
        self.screen.fill((30, 30, 40))
        self.menu.draw_centered(self.screen, "2D像素闯关游戏")
        pygame.display.flip()

    def draw_pause(self):
        self.draw_world(self.screen)
        # 半透明遮罩
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))
        # 文字
        font = pygame.font.SysFont("SimHei", 36)
        txt = font.render("暂停 - Esc返回", True, WHITE)
        self.screen.blit(txt, (SCREEN_W//2 - txt.get_width()//2, SCREEN_H//2 - 20))
        pygame.display.flip()

    def draw_describle(self):
        self.screen.fill((0,0,0))
        #文字
        font = pygame.font.SysFont("SimHei",30)
        lines = [
        '操作说明：',
        'A/D: 左右移动',
        '空格：跳跃（在地面）',
        'S: 蹲下（减少抵触高度）',
        'K: 发射火球（朝当前朝向）',
        'ESC: 暂停/继续',
        'E:查询告示牌 进入门',
        "P 返回",
        ]
        for idx, l in enumerate(lines):
            t = font.render(l, True, (230,230,230))
            self.screen.blit(t, (60, 60 + idx*34))
        
        pygame.display.flip()
