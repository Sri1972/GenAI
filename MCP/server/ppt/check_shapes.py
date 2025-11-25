"""Check available MSO_SHAPE constants"""

from pptx.enum.shapes import MSO_SHAPE

print("Available MSO_SHAPE constants:")
for attr in dir(MSO_SHAPE):
    if not attr.startswith('_'):
        try:
            value = getattr(MSO_SHAPE, attr)
            print(f"  {attr}: {value}")
        except:
            pass

# Check specific ones we're using
print("\nChecking our mapped shapes:")
shapes_to_check = [
    "OVAL", "RECTANGLE", "ROUNDED_RECTANGLE", "REGULAR_PENTAGON",
    "HEXAGON", "OCTAGON", "ISOSCELES_TRIANGLE", "DIAMOND",
    "RIGHT_ARROW", "STAR_5", "STAR_6", "STAR_7", "CLOUD",
    "HEART", "LIGHTNING_BOLT", "SUN", "MOON"
]

for shape_name in shapes_to_check:
    if hasattr(MSO_SHAPE, shape_name):
        print(f"✓ {shape_name}")
    else:
        print(f"✗ {shape_name} NOT FOUND")
