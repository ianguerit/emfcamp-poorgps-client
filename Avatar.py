import math
import random
import machine

# 1. Byte-generation: Convert any string into a 6-byte list deterministically
def handle_to_bytes(handle: str) -> list:
    """
    Hashes a string into 6 deterministic bytes using a rolling shift.
    This replaces the hardware MAC address bytes.
    """
    bytes_out = [0, 0, 0, 0, 0, 0]
    for i, char in enumerate(handle):
        # Distribute the character's ASCII value across the 6 slots
        slot = i % 6
        # A simple rolling XOR and add to mix the characters thoroughly
        bytes_out[slot] = (bytes_out[slot] ^ ord(char)) + i
        bytes_out[slot] %= 256
        
    # Ensure no completely dead zeros to keep the math interesting
    return [b if b != 0 else (i + 42) for i, b in enumerate(bytes_out)]

# 2. Random Handle Generator for first-time setup
def generate_random_handle() -> str:
    adjectives = ["Space", "Cosmic", "Neon", "Quantum", "Cyber", "Solar", "Pixel"]
    nouns = ["Goat", "Pilot", "Badge", "Hacker", "Ranger", "Bot", "Vector"]
    
    # Use hardware noise for the random seed if available
    try:
        random.seed(machine.rng())
    except AttributeError:
        pass
        
    adj = random.choice(adjectives)
    noun = random.choice(nouns)
    num = random.randint(10, 99)
    
    return f"{adj}{noun}{num}" # E.g., "NeonHacker42"

# 3. Avatar Renderer (Expects a string handle now)
def draw_handle_avatar(ctx, handle: str, size=40):
    # Convert their custom string into our 6 pseudo-MAC bytes
    avatar_bytes = handle_to_bytes(handle)
    
    num_sides = 3 + (avatar_bytes[2] % 6)       
    layers = 3 + (avatar_bytes[3] % 3)          
    rotation_step = (avatar_bytes[4] % 45) + 10 
    base_hue = avatar_bytes[5] / 255.0
    
    ctx.save()
    ctx.line_width = 2.0
    
    for i in range(layers):
        radius = size - (i * (size / layers))
        r = (base_hue + (i * 0.23)) % 1.0
        g = (base_hue + (i * 0.61)) % 1.0
        b = 1.0 - r
        
        ctx.rgb(r, g, b)
        ctx.rotate(math.radians(rotation_step * i))
        
        ctx.begin_path()
        for side in range(num_sides):
            angle = (2 * math.pi * side) / num_sides
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            
            if side == 0:
                ctx.move_to(x, y)
            else:
                ctx.line_to(x, y)
        ctx.close_path()
        
        if i % 2 == 0:
            ctx.stroke()
        else:
            ctx.rgba(r, g, b, 0.25)
            ctx.fill()
            
    ctx.restore()
