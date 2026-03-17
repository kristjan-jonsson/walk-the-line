import sys
sys.path.insert(0, '.')
from level import LevelGenerator

# Test 1: default (no file)
gen = LevelGenerator()
gen.update(500)
print(f"Default OK: segments={len(gen.segments)}, stars={len(gen.stars)}")

# Test 2: from_file default.json
gen2 = LevelGenerator.from_file('levels/default.json')
gen2.update(500)
print(f"default.json OK: segments={len(gen2.segments)}, stars={len(gen2.stars)}")

# Test 3: from_file easy.json
gen3 = LevelGenerator.from_file('levels/easy.json')
gen3.update(500)
print(f"easy.json OK: segments={len(gen3.segments)}, stars={len(gen3.stars)}")

# Test 4: from_file hard.json
gen4 = LevelGenerator.from_file('levels/hard.json')
gen4.update(500)
print(f"hard.json OK: segments={len(gen4.segments)}, stars={len(gen4.stars)}")

# Test 5: seamless mid-run transition
gen5 = LevelGenerator.from_file('levels/hard.json', start_x=3000.0, start_y=350.0)
gen5.update(3100)
print(f"Seamless transition OK: x_range={gen5.segments[0].x1:.0f}..{gen5.segments[-1].x2:.0f}")
