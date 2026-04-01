import pygame
import sys
import random
import math
import time

pygame.init()

# ========================= CONFIGURATION =========================

WINDOW_W = 580
WINDOW_H = 720
FPS = 60
NUM_COLORS = 3

# ASMR palette — soft, muted, warm
BG_TOP = (22, 22, 34)
BG_BOT = (28, 26, 40)

TILE_COLORS = [
    (224, 122, 114),   # soft coral
    (122, 190, 148),   # sage green
    (152, 134, 194),   # lavender
]

SHADOW_BASE = (12, 12, 22)
TEXT_COLOR = (205, 200, 212)
TEXT_DIM = (95, 90, 108)
FLASH_COLOR = (255, 255, 255)
BUTTON_IDLE = (52, 48, 68)
BUTTON_HOVER = (72, 66, 92)
WIN_TEXT_COLOR = (255, 222, 160)

# Arrow visuals
ARROW_STATIC_ALPHA = 28       # pre-shown arrows
ARROW_DISCOVERED_ALPHA = 22   # arrows revealed by clicking
ARROW_DISCOVERED_COLOR = (180, 220, 255)  # slightly blue tint for discovered

# Tile geometry
TILE_RADIUS = 14
TILE_GAP = 14
SHADOW_OFFSET = 5
SHADOW_EXTRA = 4

# Animation timing (seconds)
FLIP_DUR = 0.20
POP_DUR = 0.30
POP_PEAK = 1.10
NEIGHBOR_STAGGER = 0.065
FLASH_DUR = 0.35
IDLE_BREATH_AMP = 0.008
IDLE_BREATH_SPEED = 1.6
WIN_PULSE_SPEED = 1.4
WIN_PULSE_SCALE = 0.025
WIN_PULSE_BRIGHT = 18
WIN_FADE_IN = 0.4

# Discovery modes
DISC_VISIBLE = 'visible'      # all arrows shown from the start
DISC_DISCOVER = 'discover'    # arrows hidden until you click, then persist
DISC_MEMORY = 'memory'        # flash only, nothing persists

# ========================= EASING =========================

def ease_out_cubic(t):
    return 1.0 - (1.0 - t) ** 3

def ease_out_back(t):
    c = 1.70158
    return 1.0 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2

def clamp01(t):
    return max(0.0, min(1.0, t))

def lerp_color(c1, c2, t):
    t = clamp01(t)
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))

def brighten(color, amount):
    return tuple(min(255, c + amount) for c in color)

# ========================= PRE-RENDERED ASSETS =========================

_bg_surface = None

def get_bg_surface():
    global _bg_surface
    if _bg_surface is None:
        _bg_surface = pygame.Surface((WINDOW_W, WINDOW_H))
        for y in range(WINDOW_H):
            t = y / WINDOW_H
            c = lerp_color(BG_TOP, BG_BOT, t)
            pygame.draw.line(_bg_surface, c, (0, y), (WINDOW_W, y))
    return _bg_surface

# ========================= TILE =========================

class Tile:
    __slots__ = (
        'row', 'col', 'color', 'prev_color',
        'x', 'y', 'size',
        'flip_t0', 'pop_t0',
        'breath_phase',
    )

    def __init__(self, row, col):
        self.row = row
        self.col = col
        self.color = 0
        self.prev_color = 0
        self.x = 0
        self.y = 0
        self.size = 0
        self.flip_t0 = -1.0
        self.pop_t0 = -1.0
        self.breath_phase = random.uniform(0, math.tau)

    def place(self, x, y, size):
        self.x = x
        self.y = y
        self.size = size

    def flip(self, now, delay=0.0):
        self.prev_color = self.color
        self.color = (self.color + 1) % NUM_COLORS
        self.flip_t0 = now + delay
        self.pop_t0 = now + delay

    def flip_silent(self):
        self.color = (self.color + 1) % NUM_COLORS
        self.prev_color = self.color

    def _render_color(self, now):
        if self.flip_t0 < 0 or now < self.flip_t0:
            idx = self.prev_color if self.flip_t0 >= 0 else self.color
            return TILE_COLORS[idx]
        t = clamp01((now - self.flip_t0) / FLIP_DUR)
        t = ease_out_cubic(t)
        if t >= 1.0:
            self.flip_t0 = -1.0
        return lerp_color(TILE_COLORS[self.prev_color], TILE_COLORS[self.color], t)

    def _scale(self, now):
        pop = 1.0
        if self.pop_t0 >= 0 and now >= self.pop_t0:
            t = clamp01((now - self.pop_t0) / POP_DUR)
            if t >= 1.0:
                self.pop_t0 = -1.0
            else:
                if t < 0.35:
                    s = ease_out_cubic(t / 0.35)
                    pop = 1.0 + (POP_PEAK - 1.0) * s
                else:
                    s = ease_out_cubic((t - 0.35) / 0.65)
                    pop = POP_PEAK - (POP_PEAK - 1.0) * s

        breath = 1.0 + IDLE_BREATH_AMP * math.sin(now * IDLE_BREATH_SPEED * math.tau + self.breath_phase)
        return pop * breath

    def draw(self, surf, now, win=False):
        color = self._render_color(now)
        scale = self._scale(now)

        if win:
            p = (math.sin(now * math.tau / WIN_PULSE_SPEED) + 1.0) * 0.5
            scale += p * WIN_PULSE_SCALE
            color = brighten(color, int(p * WIN_PULSE_BRIGHT))

        sz = int(self.size * scale)
        off = (self.size - sz) // 2
        rx, ry = self.x + off, self.y + off

        # Shadow
        sh_rect = pygame.Rect(rx - SHADOW_EXTRA // 2,
                               ry + SHADOW_OFFSET - SHADOW_EXTRA // 2,
                               sz + SHADOW_EXTRA, sz + SHADOW_EXTRA)
        shadow = pygame.Surface((sh_rect.w, sh_rect.h), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (*SHADOW_BASE, 38),
                         (0, 0, sh_rect.w, sh_rect.h),
                         border_radius=TILE_RADIUS + 2)
        surf.blit(shadow, sh_rect.topleft)

        # Main tile
        tile_rect = pygame.Rect(rx, ry, sz, sz)
        pygame.draw.rect(surf, color, tile_rect, border_radius=TILE_RADIUS)

        # Inner highlight
        hl_color = brighten(color, 22)
        hl_w = sz - 10
        hl_h = max(1, sz // 4)
        if hl_w > 0 and hl_h > 0:
            hl_surf = pygame.Surface((hl_w, hl_h), pygame.SRCALPHA)
            pygame.draw.rect(hl_surf, (*hl_color, 35),
                             (0, 0, hl_w, hl_h),
                             border_radius=TILE_RADIUS - 3)
            surf.blit(hl_surf, (rx + 5, ry + 3))

# ========================= ADJACENCY =========================

def _make_one_to_one_random(rows, cols):
    """Each tile gets exactly 1 outgoing AND exactly 1 incoming connection.
    Uses a random derangement — a permutation where no tile maps to itself.
    This prevents multiple tiles piling onto the same target."""
    tiles = [(r, c) for r in range(rows) for c in range(cols)]
    n = len(tiles)
    # Generate a derangement (permutation with no fixed points)
    while True:
        perm = list(range(n))
        random.shuffle(perm)
        if all(perm[i] != i for i in range(n)):
            break
    adj = {}
    for i, tile in enumerate(tiles):
        adj[tile] = [tiles[perm[i]]]
    return adj

def _make_one_to_one_structured(rows, cols, direction):
    """Each tile connects to its neighbor in the given direction.
    Tiles on the boundary with no neighbor in that direction get no connection (orphans)."""
    adj = {(r, c): [] for r in range(rows) for c in range(cols)}
    dr, dc = {'right': (0, 1), 'down': (1, 0), 'left': (0, -1), 'up': (-1, 0)}[direction]
    for r in range(rows):
        for c in range(cols):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                adj[(r, c)] = [(nr, nc)]
    return adj

def _make_one_to_one_structured_full(rows, cols, direction):
    """Like structured, but boundary tiles wrap around so every tile has exactly 1 connection."""
    adj = {}
    dr, dc = {'right': (0, 1), 'down': (1, 0), 'left': (0, -1), 'up': (-1, 0)}[direction]
    for r in range(rows):
        for c in range(cols):
            nr, nc = (r + dr) % rows, (c + dc) % cols
            if (nr, nc) == (r, c):
                # Degenerate (1-wide grid in wrap direction), pick any other
                others = [(rr, cc) for rr in range(rows) for cc in range(cols) if (rr, cc) != (r, c)]
                adj[(r, c)] = [random.choice(others)] if others else []
            else:
                adj[(r, c)] = [(nr, nc)]
    return adj

def make_adjacency(rows, cols, pattern):
    """Build adjacency dict: tile -> list of 0 or 1 targets."""
    if pattern == 'right':
        return _make_one_to_one_structured(rows, cols, 'right')
    elif pattern == 'down':
        return _make_one_to_one_structured(rows, cols, 'down')
    elif pattern == 'right_wrap':
        return _make_one_to_one_structured_full(rows, cols, 'right')
    elif pattern == 'down_wrap':
        return _make_one_to_one_structured_full(rows, cols, 'down')
    elif pattern == 'random':
        return _make_one_to_one_random(rows, cols)
    else:
        return {(r, c): [] for r in range(rows) for c in range(cols)}

# ========================= LEVELS =========================

LEVELS = [
    # --- 2x2: learn the mechanic ---
    # L1: tiny grid, right arrows shown, just click around
    {'rows': 2, 'cols': 2, 'pattern': 'right',      'discovery': DISC_VISIBLE,  'clicks': 2},
    # L2: down arrows, still trivial
    {'rows': 2, 'cols': 2, 'pattern': 'down',        'discovery': DISC_VISIBLE,  'clicks': 2},
    # L3: wrap so every tile has a connection
    {'rows': 2, 'cols': 2, 'pattern': 'right_wrap',  'discovery': DISC_VISIBLE,  'clicks': 2},

    # --- 2x3: a little more to think about ---
    # L4: structured, visible
    {'rows': 2, 'cols': 3, 'pattern': 'right',       'discovery': DISC_VISIBLE,  'clicks': 2},
    # L5: wrap, visible
    {'rows': 2, 'cols': 3, 'pattern': 'down_wrap',   'discovery': DISC_VISIBLE,  'clicks': 2},
    # L6: introduce discover mode on a small grid
    {'rows': 2, 'cols': 3, 'pattern': 'right_wrap',  'discovery': DISC_DISCOVER, 'clicks': 2},
    # L7: random connections, discover mode
    {'rows': 2, 'cols': 3, 'pattern': 'random',      'discovery': DISC_DISCOVER, 'clicks': 3},

    # --- 3x3: the full game ---
    # L8: structured, visible — ease into bigger grid
    {'rows': 3, 'cols': 3, 'pattern': 'right_wrap',  'discovery': DISC_VISIBLE,  'clicks': 3},
    # L9: random, discover — learn the connections
    {'rows': 3, 'cols': 3, 'pattern': 'random',      'discovery': DISC_DISCOVER, 'clicks': 3},
    # L10: random, discover, harder scramble
    {'rows': 3, 'cols': 3, 'pattern': 'random',      'discovery': DISC_DISCOVER, 'clicks': 4},
    # L11+: memory mode — pure recall
    {'rows': 3, 'cols': 3, 'pattern': 'random',      'discovery': DISC_MEMORY,   'clicks': 3},
    {'rows': 3, 'cols': 3, 'pattern': 'random',      'discovery': DISC_MEMORY,   'clicks': 4},
    {'rows': 3, 'cols': 3, 'pattern': 'random',      'discovery': DISC_MEMORY,   'clicks': 5},
]

# ========================= ARROW DRAWING HELPERS =========================

def _draw_arrow_on_surface(surf, sx, sy, tx, ty, tile_size, color, alpha):
    """Draw a single directed arrow from (sx,sy) to (tx,ty) on an SRCALPHA surface."""
    angle = math.atan2(ty - sy, tx - sx)
    pullback = tile_size // 2 + 2
    ex = tx - pullback * math.cos(angle)
    ey = ty - pullback * math.sin(angle)

    pygame.draw.line(surf, (*color, alpha), (sx, sy), (int(ex), int(ey)), 2)

    al = 8
    a1x = ex - al * math.cos(angle - 0.45)
    a1y = ey - al * math.sin(angle - 0.45)
    a2x = ex - al * math.cos(angle + 0.45)
    a2y = ey - al * math.sin(angle + 0.45)
    pygame.draw.polygon(surf, (*color, alpha + 14),
                        [(int(ex), int(ey)),
                         (int(a1x), int(a1y)),
                         (int(a2x), int(a2y))])

# ========================= GAME =========================

class Game:
    def __init__(self, screen=None, clock=None, fonts=None):
        if screen is None:
            self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
            pygame.display.set_caption("The Flippening")
        else:
            self.screen = screen

        self.clock = clock or pygame.time.Clock()

        if fonts:
            self.font_lg, self.font_md, self.font_sm = fonts
        else:
            for name in ('Helvetica Neue', 'Helvetica', 'Arial', None):
                try:
                    self.font_lg = pygame.font.SysFont(name, 30)
                    self.font_md = pygame.font.SysFont(name, 20)
                    self.font_sm = pygame.font.SysFont(name, 15)
                    break
                except Exception:
                    continue

        self.level_idx = 0
        self.tiles = {}
        self.adj = {}
        self.rows = self.cols = 0
        self.discovery = DISC_VISIBLE
        self.tile_size = 0
        self.grid_x = self.grid_y = 0
        self.solved = False
        self.solve_time = 0.0
        self.moves = 0
        self.btn_rect = pygame.Rect(0, 0, 0, 0)
        self.flashes = []              # (src, dst, t0)
        self.arrow_surf = None         # cached static arrow overlay (visible mode)
        self.discovered = set()        # set of (src, dst) pairs revealed in discover mode
        self.discovered_surf = None    # rebuilt when discovered set changes
        self.hovered_tile = None

        # Back button
        self.back_rect = pygame.Rect(20, WINDOW_H - 58, 90, 36)

        self.load_level(0)

    # ----- level management -----

    def load_level(self, idx):
        self.level_idx = idx
        defn = LEVELS[min(idx, len(LEVELS) - 1)]
        self.rows, self.cols = defn['rows'], defn['cols']
        self.discovery = defn['discovery']
        self.adj = make_adjacency(self.rows, self.cols, defn['pattern'])

        # Tile sizing
        max_w = WINDOW_W - 80
        max_h = WINDOW_H - 260
        tw = (max_w - (self.cols - 1) * TILE_GAP) // self.cols
        th = (max_h - (self.rows - 1) * TILE_GAP) // self.rows
        self.tile_size = min(tw, th, 100)

        total_w = self.cols * self.tile_size + (self.cols - 1) * TILE_GAP
        total_h = self.rows * self.tile_size + (self.rows - 1) * TILE_GAP
        self.grid_x = (WINDOW_W - total_w) // 2
        self.grid_y = 130 + (max_h - total_h) // 2

        self.tiles = {}
        for r in range(self.rows):
            for c in range(self.cols):
                t = Tile(r, c)
                t.place(
                    self.grid_x + c * (self.tile_size + TILE_GAP),
                    self.grid_y + r * (self.tile_size + TILE_GAP),
                    self.tile_size,
                )
                self.tiles[(r, c)] = t

        self._gen_puzzle(defn.get('clicks', 3))
        self.solved = False
        self.solve_time = 0.0
        self.moves = 0
        self.flashes = []
        self.hovered_tile = None
        self.discovered = set()
        self.discovered_surf = None
        self._build_arrow_surface()

        bw, bh = 150, 42
        self.btn_rect = pygame.Rect((WINDOW_W - bw) // 2, WINDOW_H - 72, bw, bh)

    def _gen_puzzle(self, max_clicks):
        for t in self.tiles.values():
            t.color = 0
            t.prev_color = 0
        positions = list(self.tiles.keys())
        n = random.randint(2, max_clicks)
        chosen = random.sample(positions, min(n, len(positions)))
        for pos in chosen:
            times = random.randint(1, NUM_COLORS - 1)
            for _ in range(times):
                self.tiles[pos].flip_silent()
                for nb in self.adj.get(pos, []):
                    self.tiles[nb].flip_silent()
        if self._check_solved():
            pos = random.choice(positions)
            self.tiles[pos].flip_silent()
            for nb in self.adj.get(pos, []):
                self.tiles[nb].flip_silent()

    def _check_solved(self):
        vals = set(t.color for t in self.tiles.values())
        return len(vals) == 1

    # ----- arrow surfaces -----

    def _build_arrow_surface(self):
        """Pre-render static arrows for visible mode."""
        if self.discovery != DISC_VISIBLE:
            self.arrow_surf = None
            return
        self.arrow_surf = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        half = self.tile_size // 2
        for src, targets in self.adj.items():
            sx = self.tiles[src].x + half
            sy = self.tiles[src].y + half
            for dst in targets:
                tx = self.tiles[dst].x + half
                ty = self.tiles[dst].y + half
                _draw_arrow_on_surface(self.arrow_surf, sx, sy, tx, ty,
                                       self.tile_size, (255, 255, 255), ARROW_STATIC_ALPHA)

    def _rebuild_discovered_surface(self):
        """Rebuild the overlay showing discovered connections."""
        self.discovered_surf = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        half = self.tile_size // 2
        for src, dst in self.discovered:
            sx = self.tiles[src].x + half
            sy = self.tiles[src].y + half
            tx = self.tiles[dst].x + half
            ty = self.tiles[dst].y + half
            _draw_arrow_on_surface(self.discovered_surf, sx, sy, tx, ty,
                                   self.tile_size, ARROW_DISCOVERED_COLOR, ARROW_DISCOVERED_ALPHA)

    # ----- input -----

    def _tile_at(self, mx, my):
        for pos, t in self.tiles.items():
            if t.x <= mx < t.x + t.size and t.y <= my < t.y + t.size:
                return pos
        return None

    def _click_tile(self, pos):
        if self.solved:
            return
        now = time.time()
        self.moves += 1
        self.tiles[pos].flip(now)

        neighbors = self.adj.get(pos, [])
        for i, nb in enumerate(neighbors):
            delay = (i + 1) * NEIGHBOR_STAGGER
            self.tiles[nb].flip(now, delay)
            self.flashes.append((pos, nb, now + delay * 0.4))

            # Discover mode: permanently reveal this connection
            if self.discovery == DISC_DISCOVER:
                edge = (pos, nb)
                if edge not in self.discovered:
                    self.discovered.add(edge)
                    self._rebuild_discovered_surface()

        if self._check_solved():
            self.solved = True
            self.solve_time = now

    # ----- drawing -----

    def _draw_flashes(self, now):
        alive = []
        half = self.tile_size // 2
        overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        drew = False

        for src, dst, t0 in self.flashes:
            if now < t0:
                alive.append((src, dst, t0))
                continue
            t = (now - t0) / FLASH_DUR
            if t > 1.0:
                continue
            alive.append((src, dst, t0))
            drew = True
            alpha = int(100 * (1.0 - ease_out_cubic(t)))
            sx = self.tiles[src].x + half
            sy = self.tiles[src].y + half
            tx = self.tiles[dst].x + half
            ty = self.tiles[dst].y + half
            for w, am in ((5, 0.25), (2, 0.7), (1, 1.0)):
                pygame.draw.line(overlay, (*FLASH_COLOR, int(alpha * am)),
                                 (sx, sy), (tx, ty), w)
        self.flashes = alive
        if drew:
            self.screen.blit(overlay, (0, 0))

    def _draw_hover(self, now):
        if self.hovered_tile is None or self.solved:
            return
        t = self.tiles[self.hovered_tile]
        sz = t.size + 6
        off = (t.size - sz) // 2
        hover_surf = pygame.Surface((sz, sz), pygame.SRCALPHA)
        color = t._render_color(now)
        pygame.draw.rect(hover_surf, (*color, 18), (0, 0, sz, sz),
                         border_radius=TILE_RADIUS + 2)
        self.screen.blit(hover_surf, (t.x + off, t.y + off))

    def _draw_ui(self, now):
        # Level
        lt = self.font_md.render(f"Level {self.level_idx + 1}", True, TEXT_DIM)
        self.screen.blit(lt, ((WINDOW_W - lt.get_width()) // 2, 32))

        # Moves
        mt = self.font_sm.render(f"moves  {self.moves}", True, TEXT_DIM)
        self.screen.blit(mt, ((WINDOW_W - mt.get_width()) // 2, 58))

        # Discovery mode hint
        if self.discovery == DISC_DISCOVER:
            hint = self.font_sm.render("click to reveal connections", True, TEXT_DIM)
            self.screen.blit(hint, ((WINDOW_W - hint.get_width()) // 2, 78))
        elif self.discovery == DISC_MEMORY:
            hint = self.font_sm.render("watch carefully", True, TEXT_DIM)
            self.screen.blit(hint, ((WINDOW_W - hint.get_width()) // 2, 78))

        # Win text
        if self.solved:
            elapsed = now - self.solve_time
            alpha = min(255, int(255 * elapsed / WIN_FADE_IN))
            p = (math.sin(now * math.tau / WIN_PULSE_SPEED) + 1.0) * 0.5
            sc = 1.0 + p * 0.04

            wt = self.font_lg.render("unified", True, WIN_TEXT_COLOR)
            sw = int(wt.get_width() * sc)
            sh = int(wt.get_height() * sc)
            wt = pygame.transform.smoothscale(wt, (sw, sh))

            tmp = pygame.Surface((sw, sh), pygame.SRCALPHA)
            tmp.blit(wt, (0, 0))
            tmp.set_alpha(alpha)
            self.screen.blit(tmp, ((WINDOW_W - sw) // 2, 86))

        # Button
        mx, my = pygame.mouse.get_pos()
        hov = self.btn_rect.collidepoint(mx, my)
        bc = BUTTON_HOVER if hov else BUTTON_IDLE
        pygame.draw.rect(self.screen, bc, self.btn_rect, border_radius=10)

        label = "next" if self.solved else "reset"
        bt = self.font_md.render(label, True, TEXT_COLOR)
        self.screen.blit(bt, (self.btn_rect.centerx - bt.get_width() // 2,
                               self.btn_rect.centery - bt.get_height() // 2))

        # Back button
        hov = self.back_rect.collidepoint(mx, my)
        bc = BUTTON_HOVER if hov else BUTTON_IDLE
        pygame.draw.rect(self.screen, bc, self.back_rect, border_radius=8)
        bk = self.font_sm.render("back", True, TEXT_COLOR)
        self.screen.blit(bk, (self.back_rect.centerx - bk.get_width() // 2,
                               self.back_rect.centery - bk.get_height() // 2))

    # ----- main loop -----

    def run(self):
        """Returns True if user clicks back (to menu), False if quit."""
        while True:
            now = time.time()

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return False

                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    mx, my = ev.pos
                    if self.back_rect.collidepoint(mx, my):
                        return True
                    if self.btn_rect.collidepoint(mx, my):
                        if self.solved:
                            self.load_level(self.level_idx + 1)
                        else:
                            self.load_level(self.level_idx)
                        continue
                    pos = self._tile_at(mx, my)
                    if pos is not None:
                        self._click_tile(pos)

                if ev.type == pygame.MOUSEMOTION:
                    self.hovered_tile = self._tile_at(*ev.pos)

            # Render
            self.screen.blit(get_bg_surface(), (0, 0))

            # Arrows: static (visible mode) or discovered overlay
            if self.arrow_surf:
                self.screen.blit(self.arrow_surf, (0, 0))
            if self.discovered_surf:
                self.screen.blit(self.discovered_surf, (0, 0))

            self._draw_flashes(now)
            self._draw_hover(now)

            for tile in self.tiles.values():
                tile.draw(self.screen, now, win=self.solved)

            self._draw_ui(now)

            pygame.display.flip()
            self.clock.tick(FPS)

# ========================= MODE SELECT =========================

class ModeSelect:
    def __init__(self, screen, clock, fonts):
        self.screen = screen
        self.clock = clock
        self.font_lg, self.font_md, self.font_sm = fonts

        bw, bh = 200, 50
        cx = WINDOW_W // 2
        self.campaign_btn = pygame.Rect(cx - bw // 2, 320, bw, bh)
        self.endless_btn = pygame.Rect(cx - bw // 2, 400, bw, bh)

    def run(self):
        """Returns 'campaign', 'endless', or None (quit)."""
        while True:
            now = time.time()
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return None
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    mx, my = ev.pos
                    if self.campaign_btn.collidepoint(mx, my):
                        return 'campaign'
                    if self.endless_btn.collidepoint(mx, my):
                        return 'endless'

            self.screen.blit(get_bg_surface(), (0, 0))

            # Title
            title = self.font_lg.render("the flippening", True, TEXT_COLOR)
            self.screen.blit(title, ((WINDOW_W - title.get_width()) // 2, 180))

            # Subtitle
            sub = self.font_sm.render("a directional flip puzzle", True, TEXT_DIM)
            self.screen.blit(sub, ((WINDOW_W - sub.get_width()) // 2, 225))

            mx, my = pygame.mouse.get_pos()

            # Campaign button
            hov = self.campaign_btn.collidepoint(mx, my)
            bc = BUTTON_HOVER if hov else BUTTON_IDLE
            pygame.draw.rect(self.screen, bc, self.campaign_btn, border_radius=12)
            bt = self.font_md.render("campaign", True, TEXT_COLOR)
            self.screen.blit(bt, (self.campaign_btn.centerx - bt.get_width() // 2,
                                   self.campaign_btn.centery - bt.get_height() // 2))

            # Endless button
            hov = self.endless_btn.collidepoint(mx, my)
            bc = BUTTON_HOVER if hov else BUTTON_IDLE
            pygame.draw.rect(self.screen, bc, self.endless_btn, border_radius=12)
            bt = self.font_md.render("endless", True, TEXT_COLOR)
            self.screen.blit(bt, (self.endless_btn.centerx - bt.get_width() // 2,
                                   self.endless_btn.centery - bt.get_height() // 2))

            # Hint
            hint = self.font_sm.render("click to begin", True, TEXT_DIM)
            p = (math.sin(now * 2.0) + 1.0) * 0.5
            hint.set_alpha(int(120 + 80 * p))
            self.screen.blit(hint, ((WINDOW_W - hint.get_width()) // 2, 490))

            pygame.display.flip()
            self.clock.tick(FPS)

# ========================= ENTRY =========================

def main():
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption("The Flippening")
    clock = pygame.time.Clock()

    for name in ('Helvetica Neue', 'Helvetica', 'Arial', None):
        try:
            font_lg = pygame.font.SysFont(name, 30)
            font_md = pygame.font.SysFont(name, 20)
            font_sm = pygame.font.SysFont(name, 15)
            break
        except Exception:
            continue

    fonts = (font_lg, font_md, font_sm)

    while True:
        menu = ModeSelect(screen, clock, fonts)
        choice = menu.run()

        if choice is None:
            break
        elif choice == 'campaign':
            game = Game(screen, clock, fonts)
            back = game.run()
            if not back:
                break
        elif choice == 'endless':
            from endless import EndlessGame
            eg = EndlessGame(screen, clock, fonts)
            back = eg.run()
            if not back:
                break

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
