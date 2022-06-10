from math import atan, pow, atanh, pi, cos, sin

from fixedpoint import FixedPoint

NUM_ITER = 32
K = FixedPoint(0.5, m=15, n=16, signed=True)

def cir_LUT(i) -> FixedPoint:
    return FixedPoint(atan(pow(2, -i)), m=14, n=16, signed=True)

def lin_LUT(i) -> FixedPoint:
    return FixedPoint(pow(2, -i), m=14, n=16, signed=True)

def hyp_LUT(i) -> FixedPoint:
    return FixedPoint(atanh(pow(2, -i)))

def cordic(x:FixedPoint, y: FixedPoint, z: FixedPoint, mode: str, mu: int):
    i = 0
    X = [x] * NUM_ITER
    Y = [y] * NUM_ITER
    Z = [z] * NUM_ITER
    for i in range(NUM_ITER):
        # if i == 0:
        #     continue
        if (mode == "rotation"):
            if (z > 0):
                d = 1
            else:
                d = -1
        elif(mode == "vectoring"):
            if (x * y < 0):
                d = 1
            else:
                d = -1
        if (mu == 1):
            e = cir_LUT(i)
        elif (mu == 0):
            e = lin_LUT(i)
        elif (mu == -1):
            e = hyp_LUT(i)
        x = x - mu * d * (y >> i)
        y = y + d * (x >> i)
        z = z - d * e
        X[i] = x
        Y[i] = y
        Z[i] = z
    return (X[NUM_ITER-1], Y[NUM_ITER-1], Z[NUM_ITER-1])

if __name__ == "__main__":
    angle = FixedPoint(pi/3, m=16, n=16, signed=True)
    x = FixedPoint(0.5, m=14, n=16, signed=True)
    y = FixedPoint(0, m=14, n=16, signed=True)
    z = FixedPoint(0.5, m=14, n=16, signed=True)
    sol = cordic(x=x, y=y, z=z, mode="rotation", mu=0)
    print(f"Results:   X: {hex(sol[0])} Y: {hex(sol[1])} Z: {hex(sol[2])}")
    print(f"Results:   X: {float(sol[0])} Y: {float(sol[1])} Z: {float(sol[2])}")
    # print("Expected:  X: {} Y: {} Z: {}".format(cos(angle), sin(angle), 0))