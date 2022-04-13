from fixedpoint import FixedPoint
from math import pi, cos, sin, atanh

x = FixedPoint(cos(pi/6), m=16, n=16, signed=True)
print(f"x: Actual: {float(x)} Int: {x}")

y = FixedPoint(sin(pi/6), m=16, n=16, signed=True)
print(f"y: Actual: {float(y)} Int: {y}")

for i in range(32):
    print(f"{i}: {hex(FixedPoint(atanh(2**(-1*(i+1))), m=14, n=16, signed=True))}")