from fixedpoint import FixedPoint
from math import pi, cos, sin

x = FixedPoint(cos(pi/6), m=16, n=16, signed=True)
print(f"x: Actual: {float(x)} Hex: {hex(x)}")

y = FixedPoint(sin(pi/6), m=16, n=16, signed=True)
print(f"y: Actual: {float(y)} Hex: {hex(y)}")

