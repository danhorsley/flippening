# The Flippening

A satisfying directional chain-flip puzzle game made in Pygame.

**Concept**  
Click tiles to flip their color and send a ripple forward along directed chains.  
The goal: make the entire grid one single color through clever propagation.

**Features**  
- Always-solvable procedurally generated puzzles  
- Smooth animated ripples along the chains  
- Juicy win moment with pulsing tiles and "UNIFIED!" celebration  
- Endless "New Puzzle" button  

Built as a fun prototype exploring asymmetric Lights Out-style mechanics with 3 colors and directional flow.

Because flips are directional and chained, every click creates a satisfying ripple effect that travels downstream. Solving requires planning ahead and "chasing" the effects backward through the chains.

### Core Features
- Procedurally generated puzzles that are **always solvable**
- Smooth animated chain reactions with ripple timing
- Strong win moment with pulsing tiles and "UNIFIED!" celebration
- One-click "New Puzzle" for endless play
- Built with clean mod-3 linear algebra under the hood (generate-from-solution method)

### Goals
- Create a fun, addictive flip puzzle with a fresh directional twist
- Make chain reactions feel satisfying and visually clear
- Keep early levels approachable while allowing deeper strategic play
- Prototype core mechanics quickly in Pygame before considering expansion (triangle grids, variable directions, sound, mobile port, etc.)
- Explore how directional propagation changes the classic Lights Out feel

### How to Play
- Click any tile to flip it and its downstream chain
- Watch the colors ripple along the arrows
- When all tiles match one color → victory!

Current version: 4×4 grid with right + down chains.

---

Made as a quick prototype. Feedback and contributions welcome!
