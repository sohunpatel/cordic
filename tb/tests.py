from random import getrandbits
from fixedpoint import FixedPoint
from math import pi, cos, sin, atanh, sqrt

# x = FixedPoint(cos(pi/6), m=16, n=16, signed=True)
# print(f"x: Actual: {float(x)} Int: {x}")

# y = FixedPoint(sin(pi/6), m=16, n=16, signed=True)
# print(f"y: Actual: {float(y)} Int: {y}")

# for i in range(32):
#     print(f"{i}: {hex(FixedPoint(atanh(2**(-1*(i+1))), m=14, n=16, signed=True))}")

# x = 1
# for i in range(32):
#     x *= sqrt(1 + 2**(-2*i))
# print(x)

def create(func, mu=1, mode=""):
    ret = func(32)
    if mu == 1:
        while intToFloat(ret) < -pi/2 or intToFloat(ret) > pi/2:
            ret = func(32)
    elif mu == 0:
        while intToFloat(ret) < -1 or intToFloat(ret) > 1:
            ret = func(32)
    elif mu == -1:
        while intToFloat(ret) < -5 or intToFloat(ret) > 5:
            ret = func(32)
    return ret

def intToFloat(x: int) -> float:
    binary = bin(x)
    neg = False
    if binary[2] == '1' and binary.__len__() == 32:
        neg = True
        binary = bin(-x)
    f = 0
    i = 0
    msb = False
    passedB = False
    for b in binary:
        if (b == '1'):
            f = f + 2**(binary.__len__()-i-16-1)
        if (b == 'b'):
            passedB = True
            continue
        if (msb == True):
            if b == '1':
                neg = True
        if passedB:
            i = i + 1
    if neg:
        f = -f
    return f

i = -10
while i <= 10:
    x = getrandbits(32)
    print(bin(x))
    # print(intToFloat(FixedPoint(x, m=16, n=16, signed=True)))
    print(intToFloat(x))
    i = i + 1