import pygame
import sys
import random
import numpy as np
from collections import defaultdict, deque
import time

# ========================= CONFIG =========================
GRID_SIZE = 4
CELL_SIZE = 80
PADDING = 20
COLORS = [(200, 50, 50), (50, 200, 50), (50, 50, 200)]  # R, G, B
BG_COLOR = (30, 30, 40)
ARROW_COLOR = (255, 255, 255, 80)

# Animation
ANIM_DURATION = 0.4   # seconds for full ripple
PULSE_TIME = 1.2      # win pulse duration

pygame.init()
screen = pygame.display.set_mode((GRID_SIZE * CELL_SIZE + 2 * PADDING,
                                  GRID_SIZE * CELL_SIZE + 100 + 2 * PADDING))
pygame.display.set_caption("Directional Chain Flip - 3 Colors")
font = pygame.font.SysFont("Arial", 28)
small_font = pygame.font.SysFont("Arial", 18)

clock = pygame.time.Clock()

# ====================== GRID & CHAINS ======================
def build_adjacency(size):
    adj = defaultdict(list)
    for i in range(size):
        for j in range(size):
            # Right
            if j + 1 < size:
                adj[(i, j)].append((i, j + 1))
            # Down
            if i + 1 < size:
                adj[(i, j)].append((i + 1, j))
    return adj

adjacency = build_adjacency(GRID_SIZE)

# ====================== GAME STATE ======================
grid = np.zeros((GRID_SIZE, GRID_SIZE), dtype=int)   # current colors 0,1,2
animation_queue = []   # list of (pos, start_time, color_index)
win_time = 0

def is_solved():
    return np.all(grid == grid[0, 0])

# ====================== PROC GEN ======================
def generate_puzzle(size=GRID_SIZE, max_total_clicks=6, mod=3):
    global grid
    grid = np.zeros((size, size), dtype=int)
    
    # Choose a short random solution
    total_clicks = random.randint(2, max_total_clicks)
    positions = random.sample([(i,j) for i in range(size) for j in range(size)], 
                              min(total_clicks, size*size))
    
    for pos in positions:
        times = random.randint(1, mod-1)
        for _ in range(times):
            apply_flip(pos, animate=False)

def apply_flip(pos, animate=True):
    global grid
    to_flip = []
    queue = deque([pos])
    visited = set()
    
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        to_flip.append(current)
        for neigh in adjacency[current]:
            if neigh not in visited:
                queue.append(neigh)
    
    # Apply color change
    for p in to_flip:
        grid[p[0], p[1]] = (grid[p[0], p[1]] + 1) % 3
    
    # Animation
    if animate:
        start_t = time.time()
        for idx, p in enumerate(to_flip):
            delay = idx * 0.08   # ripple delay
            animation_queue.append((p, start_t + delay, grid[p[0], p[1]]))

# ====================== DRAWING ======================
def draw_grid():
    for i in range(GRID_SIZE):
        for j in range(GRID_SIZE):
            x = PADDING + j * CELL_SIZE
            y = PADDING + i * CELL_SIZE
            color = COLORS[grid[i, j]]
            
            # Pulse on win
            if win_time > 0:
                pulse = abs(np.sin((time.time() - win_time) * 8)) * 30
                color = tuple(min(255, c + int(pulse)) for c in color)
            
            pygame.draw.rect(screen, color, (x, y, CELL_SIZE, CELL_SIZE))
            pygame.draw.rect(screen, (255, 255, 255), (x, y, CELL_SIZE, CELL_SIZE), 3)
            
            # Small number for debugging
            # txt = small_font.render(str(grid[i,j]), True, (255,255,255))
            # screen.blit(txt, (x+10, y+10))

    # Draw faint arrows
    for (i,j), neighbors in adjacency.items():
        x1 = PADDING + j * CELL_SIZE + CELL_SIZE//2
        y1 = PADDING + i * CELL_SIZE + CELL_SIZE//2
        for ni, nj in neighbors:
            x2 = PADDING + nj * CELL_SIZE + CELL_SIZE//2
            y2 = PADDING + ni * CELL_SIZE + CELL_SIZE//2
            pygame.draw.line(screen, ARROW_COLOR, (x1, y1), (x2, y2), 4)

def draw_ui():
    # New Puzzle button
    btn_rect = pygame.Rect(PADDING, GRID_SIZE*CELL_SIZE + PADDING + 20, 180, 50)
    pygame.draw.rect(screen, (70, 130, 200), btn_rect)
    pygame.draw.rect(screen, (255,255,255), btn_rect, 3)
    txt = font.render("New Puzzle", True, (255,255,255))
    screen.blit(txt, (btn_rect.centerx - txt.get_width()//2, btn_rect.centery - txt.get_height()//2))
    
    if is_solved() and win_time == 0:
        win_time = time.time()  # trigger win once

    if win_time > 0:
        if time.time() - win_time < PULSE_TIME:
            txt = font.render("UNIFIED!", True, (255, 215, 0))
            scale = 1 + 0.3 * abs(np.sin((time.time() - win_time) * 10))
            big_txt = pygame.transform.scale(txt, (int(txt.get_width()*scale), int(txt.get_height()*scale)))
            screen.blit(big_txt, (screen.get_width()//2 - big_txt.get_width()//2,
                                  20))
        else:
            global win_time
            win_time = 0

# ====================== MAIN LOOP ======================
def main():
    global win_time
    generate_puzzle()   # start with one puzzle
    
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
                
            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                # Check grid click
                if PADDING <= mx < PADDING + GRID_SIZE*CELL_SIZE and PADDING <= my < PADDING + GRID_SIZE*CELL_SIZE:
                    j = (mx - PADDING) // CELL_SIZE
                    i = (my - PADDING) // CELL_SIZE
                    apply_flip((i, j))
                
                # New puzzle button
                btn_rect = pygame.Rect(PADDING, GRID_SIZE*CELL_SIZE + PADDING + 20, 180, 50)
                if btn_rect.collidepoint(mx, my):
                    generate_puzzle()
                    win_time = 0

        screen.fill(BG_COLOR)
        draw_grid()
        draw_ui()
        
        # Process animations
        current_time = time.time()
        i = 0
        while i < len(animation_queue):
            pos, start_t, target_color = animation_queue[i]
            if current_time >= start_t:
                # The actual color is already updated; we just used it for timing
                animation_queue.pop(i)
            else:
                i += 1
        
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()