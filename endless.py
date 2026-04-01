"""
Endless hex mode — larger grid, local connections, cluster clearing.
Click a hex to flip it + its one connected neighbor.
When 5+ adjacent hexes share a color, they clear and respawn.
"""

import pygame
import random
import math
import time
from collections import deque

# Reuse shared constants and helpers from main
from main import (
    WINDOW_W, WINDOW_H, FPS, NUM_COLORS,
    BG_TOP, BG_BOT, TILE_COLORS, SHADOW_BASE, TEXT_COLOR, TEXT_DIM,
    FLASH_COLOR, BUTTON_IDLE, BUTTON_HOVER, WIN_TEXT_COLOR,
    FLIP_DUR, POP_DUR, POP_PEAK, NEIGHBOR_STAGGER, FLASH_DUR,
    IDLE_BREATH_AMP, IDLE_BREATH_SPEED,
    ease_out_cubic, clamp01, lerp_color, brighten, get_bg_surface,
    _draw_arrow_on_surface,
)

# ========================= HEX CONFIG =========================

HEX_RADIUS = 30          # outer radius of each hexagon
HEX_GAP = 4              # gap between hexes
GRID_RINGS = 3            # hex rings around center (0 = just center)
                          # rings=3 gives 37 hexes
CLUSTER_MIN = 5           # adjacent same-color hexes needed to clear
MAX_EDGE_DIST = 2         # max hex distance for a connection
ARROW_ALPHA = 36          # arrows always visible in endless

# Clear animation
CLEAR_SHRINK_DUR = 0.35
SPAWN_GROW_DUR = 0.30

# ========================= HEX MATH =========================

# Axial coordinates (q, r) for hex grids
# Flat-top hexagons

def hex_to_pixel(q, r, radius, cx, cy):
    """Axial hex coord to pixel center (flat-top)."""
    x = radius * (3/2 * q)
    y = radius * (math.sqrt(3)/2 * q + math.sqrt(3) * r)
    return cx + x, cy + y

def pixel_to_hex(px, py, radius, cx, cy):
    """Pixel to fractional axial coords, then round."""
    x = px - cx
    y = py - cy
    q = (2/3 * x) / radius
    r = (-1/3 * x + math.sqrt(3)/3 * y) / radius
    return _hex_round(q, r)

def _hex_round(q, r):
    """Round fractional axial to nearest hex."""
    s = -q - r
    rq, rr, rs = round(q), round(r), round(s)
    dq, dr, ds = abs(rq - q), abs(rr - r), abs(rs - s)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return (rq, rr)

def hex_distance(a, b):
    """Axial distance between two hexes."""
    dq = a[0] - b[0]
    dr = a[1] - b[1]
    return (abs(dq) + abs(dq + dr) + abs(dr)) // 2

def hex_neighbors(q, r):
    """The 6 axial neighbors of (q, r)."""
    return [
        (q+1, r), (q-1, r),
        (q, r+1), (q, r-1),
        (q+1, r-1), (q-1, r+1),
    ]

def generate_hex_grid(rings):
    """Generate all axial coords within `rings` of the origin."""
    coords = []
    for q in range(-rings, rings + 1):
        for r in range(-rings, rings + 1):
            if hex_distance((q, r), (0, 0)) <= rings:
                coords.append((q, r))
    return coords

# ========================= HEX TILE =========================

class HexTile:
    __slots__ = (
        'q', 'r', 'color', 'prev_color',
        'cx', 'cy', 'radius',
        'flip_t0', 'pop_t0', 'breath_phase',
        'clearing', 'clear_t0',
        'spawning', 'spawn_t0',
        'points',  # cached polygon points at scale=1
    )

    def __init__(self, q, r):
        self.q = q
        self.r = r
        self.color = random.randint(0, NUM_COLORS - 1)
        self.prev_color = self.color
        self.cx = 0.0
        self.cy = 0.0
        self.radius = HEX_RADIUS
        self.flip_t0 = -1.0
        self.pop_t0 = -1.0
        self.breath_phase = random.uniform(0, math.tau)
        self.clearing = False
        self.clear_t0 = -1.0
        self.spawning = False
        self.spawn_t0 = -1.0
        self.points = []

    def place(self, cx, cy, radius):
        self.cx = cx
        self.cy = cy
        self.radius = radius
        self._build_points(radius)

    def _build_points(self, r):
        """Flat-top hexagon vertices."""
        self.points = []
        for i in range(6):
            angle = math.pi / 180 * (60 * i)
            self.points.append((
                self.cx + r * math.cos(angle),
                self.cy + r * math.sin(angle),
            ))

    def flip(self, now, delay=0.0):
        self.prev_color = self.color
        self.color = (self.color + 1) % NUM_COLORS
        self.flip_t0 = now + delay
        self.pop_t0 = now + delay

    def start_clear(self, now, delay=0.0):
        self.clearing = True
        self.clear_t0 = now + delay

    def respawn(self, now, delay=0.0):
        self.clearing = False
        self.clear_t0 = -1.0
        self.color = random.randint(0, NUM_COLORS - 1)
        self.prev_color = self.color
        self.spawning = True
        self.spawn_t0 = now + delay

    def is_alive(self, now):
        """Not mid-clear and not waiting to spawn."""
        if self.clearing:
            if self.clear_t0 >= 0 and now >= self.clear_t0:
                t = (now - self.clear_t0) / CLEAR_SHRINK_DUR
                if t >= 1.0:
                    return False
            return True  # still animating
        return True

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
        # Clear shrink
        if self.clearing and self.clear_t0 >= 0 and now >= self.clear_t0:
            t = clamp01((now - self.clear_t0) / CLEAR_SHRINK_DUR)
            return 1.0 - ease_out_cubic(t)

        # Spawn grow
        if self.spawning and self.spawn_t0 >= 0 and now >= self.spawn_t0:
            t = clamp01((now - self.spawn_t0) / SPAWN_GROW_DUR)
            if t >= 1.0:
                self.spawning = False
                self.spawn_t0 = -1.0
                return 1.0
            return ease_out_cubic(t)
        if self.spawning and (self.spawn_t0 < 0 or now < self.spawn_t0):
            return 0.0  # waiting to spawn

        # Pop
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

    def draw(self, surf, now):
        if self.clearing and self.clear_t0 >= 0 and now >= self.clear_t0:
            t = (now - self.clear_t0) / CLEAR_SHRINK_DUR
            if t >= 1.0:
                return  # fully cleared, don't draw

        scale = self._scale(now)
        if scale <= 0.01:
            return

        color = self._render_color(now)
        r = self.radius * scale

        # Build scaled points
        pts = []
        for i in range(6):
            angle = math.pi / 180 * (60 * i)
            pts.append((
                self.cx + r * math.cos(angle),
                self.cy + r * math.sin(angle),
            ))

        # Shadow
        shadow_pts = [(x, y + 4) for x, y in pts]
        shadow_surf = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        pygame.draw.polygon(shadow_surf, (*SHADOW_BASE, 30), shadow_pts)
        surf.blit(shadow_surf, (0, 0))

        # Main hex
        pygame.draw.polygon(surf, color, pts)

        # Highlight (top edge lighter)
        hl_color = brighten(color, 18)
        hl_pts = [pts[5], pts[0], pts[1]]  # top-left edge
        hl_surf = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        pygame.draw.lines(hl_surf, (*hl_color, 40), False, hl_pts, 2)
        surf.blit(hl_surf, (0, 0))

    def contains(self, px, py):
        """Point-in-hexagon test."""
        dx = abs(px - self.cx)
        dy = abs(py - self.cy)
        r = self.radius
        if dx > r or dy > r * 0.866:
            return False
        return r * 0.866 * r - r * 0.866 / 2 * dx - r / 2 * dy >= 0

# ========================= LOCAL CONNECTIONS =========================

def build_local_connections(coords, max_dist=MAX_EDGE_DIST):
    """Each hex gets exactly 1 outgoing connection to a hex within max_dist.
    Uses derangement approach: 1 in, 1 out, no self-links."""
    n = len(coords)
    idx_map = {c: i for i, c in enumerate(coords)}

    # Build a proximity-eligible list for each tile
    eligible = {}
    for i, c in enumerate(coords):
        eligible[i] = [
            j for j, c2 in enumerate(coords)
            if j != i and hex_distance(c, c2) <= max_dist
        ]

    # Try to build a derangement respecting locality constraints
    # Greedy with restarts
    for _ in range(200):
        perm = [None] * n
        used_targets = set()
        indices = list(range(n))
        random.shuffle(indices)
        ok = True

        for i in indices:
            options = [j for j in eligible[i] if j not in used_targets]
            if not options:
                ok = False
                break
            j = random.choice(options)
            perm[i] = j
            used_targets.add(j)

        if ok and all(p is not None for p in perm):
            adj = {}
            for i, c in enumerate(coords):
                adj[c] = [coords[perm[i]]]
            return adj

    # Fallback: unconstrained derangement
    while True:
        perm = list(range(n))
        random.shuffle(perm)
        if all(perm[i] != i for i in range(n)):
            break
    adj = {}
    for i, c in enumerate(coords):
        adj[c] = [coords[perm[i]]]
    return adj

# ========================= CLUSTER DETECTION =========================

def find_clusters(tiles, coords, min_size=CLUSTER_MIN):
    """Find connected groups of same-color hexes with size >= min_size.
    Uses hex grid adjacency (the 6 spatial neighbors), NOT the directed connections."""
    coord_set = set(coords)
    visited = set()
    clusters = []

    for c in coords:
        if c in visited:
            continue
        color = tiles[c].color
        # BFS for same-color contiguous region
        group = []
        queue = deque([c])
        while queue:
            cur = queue.popleft()
            if cur in visited:
                continue
            if cur not in coord_set:
                continue
            if tiles[cur].color != color:
                continue
            if tiles[cur].clearing or tiles[cur].spawning:
                continue
            visited.add(cur)
            group.append(cur)
            for nb in hex_neighbors(cur[0], cur[1]):
                if nb in coord_set and nb not in visited:
                    queue.append(nb)
        if len(group) >= min_size:
            clusters.append(group)

    return clusters

# ========================= ENDLESS GAME =========================

class EndlessGame:
    def __init__(self, screen, clock, fonts):
        self.screen = screen
        self.clock = clock
        self.font_lg, self.font_md, self.font_sm = fonts

        self.coords = generate_hex_grid(GRID_RINGS)
        self.tiles = {}
        self.adj = {}
        self.score = 0
        self.combo = 0
        self.flashes = []
        self.pending_clears = []     # (coords_list, clear_time)
        self.pending_respawns = []   # (coords_list, respawn_time)
        self.hovered_hex = None
        self.arrow_surf = None

        # Back button
        self.back_rect = pygame.Rect(20, WINDOW_H - 58, 90, 36)

        self._init_board()

    def _init_board(self):
        # Center of hex grid
        self.grid_cx = WINDOW_W // 2
        self.grid_cy = WINDOW_H // 2 - 20

        effective_r = HEX_RADIUS - HEX_GAP / 2

        self.tiles = {}
        for q, r in self.coords:
            t = HexTile(q, r)
            px, py = hex_to_pixel(q, r, HEX_RADIUS * 2 * 0.87, self.grid_cx, self.grid_cy)
            t.place(px, py, effective_r)
            self.tiles[(q, r)] = t

        self.adj = build_local_connections(self.coords, MAX_EDGE_DIST)
        self._build_arrow_surface()

        # Clear any starting clusters so board begins messy
        for _ in range(10):
            clusters = find_clusters(self.tiles, self.coords)
            if not clusters:
                break
            for cluster in clusters:
                for c in cluster:
                    self.tiles[c].color = random.randint(0, NUM_COLORS - 1)
                    self.tiles[c].prev_color = self.tiles[c].color

    def _build_arrow_surface(self):
        self.arrow_surf = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
        for src, targets in self.adj.items():
            sx, sy = self.tiles[src].cx, self.tiles[src].cy
            for dst in targets:
                tx, ty = self.tiles[dst].cx, self.tiles[dst].cy
                _draw_arrow_on_surface(self.arrow_surf, sx, sy, tx, ty,
                                       HEX_RADIUS * 2, (180, 210, 240), ARROW_ALPHA)

    def _hex_at(self, mx, my):
        # Use nearest-hex approach
        best = None
        best_d = float('inf')
        for c, t in self.tiles.items():
            d = math.hypot(mx - t.cx, my - t.cy)
            if d < t.radius and d < best_d:
                best = c
                best_d = d
        return best

    def _click_hex(self, pos):
        t = self.tiles[pos]
        if t.clearing or t.spawning:
            return

        now = time.time()
        t.flip(now)

        for i, nb in enumerate(self.adj.get(pos, [])):
            nbt = self.tiles[nb]
            if nbt.clearing or nbt.spawning:
                continue
            delay = (i + 1) * NEIGHBOR_STAGGER
            nbt.flip(now, delay)
            self.flashes.append((pos, nb, now + delay * 0.4))

        # Check for clusters after a short delay (let animations start)
        self._check_and_clear(now + 0.15)

    def _check_and_clear(self, after_time):
        clusters = find_clusters(self.tiles, self.coords)
        if not clusters:
            self.combo = 0
            return

        self.combo += 1
        all_clearing = set()
        for cluster in clusters:
            for c in cluster:
                all_clearing.add(c)
            self.score += len(cluster) * self.combo

        now = time.time()
        delay_base = max(0, after_time - now)
        for i, c in enumerate(sorted(all_clearing)):
            self.tiles[c].start_clear(now, delay_base + i * 0.025)

        respawn_time = now + delay_base + len(all_clearing) * 0.025 + CLEAR_SHRINK_DUR + 0.1
        self.pending_respawns.append((list(all_clearing), respawn_time))

    def _process_respawns(self, now):
        still_pending = []
        for coords_list, resp_time in self.pending_respawns:
            if now >= resp_time:
                for i, c in enumerate(coords_list):
                    self.tiles[c].respawn(now, i * 0.03)
                # After respawning, schedule another cluster check
                check_time = now + len(coords_list) * 0.03 + SPAWN_GROW_DUR + 0.1
                self.pending_clears.append(check_time)
            else:
                still_pending.append((coords_list, resp_time))
        self.pending_respawns = still_pending

        still_checking = []
        for check_time in self.pending_clears:
            if now >= check_time:
                self._check_and_clear(now)
            else:
                still_checking.append(check_time)
        self.pending_clears = still_checking

    def _draw_flashes(self, now):
        alive = []
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
            sx, sy = self.tiles[src].cx, self.tiles[src].cy
            tx, ty = self.tiles[dst].cx, self.tiles[dst].cy
            for w, am in ((5, 0.25), (2, 0.7), (1, 1.0)):
                pygame.draw.line(overlay, (*FLASH_COLOR, int(alpha * am)),
                                 (int(sx), int(sy)), (int(tx), int(ty)), w)
        self.flashes = alive
        if drew:
            self.screen.blit(overlay, (0, 0))

    def _draw_ui(self, now):
        # Score
        st = self.font_md.render(f"score  {self.score}", True, TEXT_COLOR)
        self.screen.blit(st, ((WINDOW_W - st.get_width()) // 2, 25))

        # Combo
        if self.combo > 1:
            ct = self.font_sm.render(f"combo x{self.combo}", True, WIN_TEXT_COLOR)
            self.screen.blit(ct, ((WINDOW_W - ct.get_width()) // 2, 52))

        # Mode label
        mt = self.font_sm.render("endless", True, TEXT_DIM)
        self.screen.blit(mt, ((WINDOW_W - mt.get_width()) // 2, WINDOW_H - 48))

        # Back button
        mx, my = pygame.mouse.get_pos()
        hov = self.back_rect.collidepoint(mx, my)
        bc = BUTTON_HOVER if hov else BUTTON_IDLE
        pygame.draw.rect(self.screen, bc, self.back_rect, border_radius=8)
        bt = self.font_sm.render("back", True, TEXT_COLOR)
        self.screen.blit(bt, (self.back_rect.centerx - bt.get_width() // 2,
                               self.back_rect.centery - bt.get_height() // 2))

    def run(self):
        """Returns True if user clicks back, False if quit."""
        while True:
            now = time.time()

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return False

                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    mx, my = ev.pos
                    if self.back_rect.collidepoint(mx, my):
                        return True
                    pos = self._hex_at(mx, my)
                    if pos is not None:
                        self._click_hex(pos)

                if ev.type == pygame.MOUSEMOTION:
                    self.hovered_hex = self._hex_at(*ev.pos)

            # Process pending respawns and chain checks
            self._process_respawns(now)

            # Render
            self.screen.blit(get_bg_surface(), (0, 0))

            if self.arrow_surf:
                self.screen.blit(self.arrow_surf, (0, 0))

            self._draw_flashes(now)

            for tile in self.tiles.values():
                tile.draw(self.screen, now)

            self._draw_ui(now)

            pygame.display.flip()
            self.clock.tick(FPS)
