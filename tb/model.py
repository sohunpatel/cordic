import math

NUM_ITER = 64
K = 0.6073

def cir_LUT(i) -> float:
    return math.atan(math.pow(2, -i))

def lin_LUT(i) -> float:
    return math.pow(2, -i)

def hyp_LUT(i) -> float:
    return math.atanh(math.pow(2, -i))

def cordic(x, y, z, mode, mu):
    i = 0
    for i in range(NUM_ITER):
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
        x = x - mu * d * math.pow(2, -i) * y
        y = y + d * math.pow(2, -i) * x
        z = z - d * e
    return (x,y, z)

if __name__ == "__main__":
    sol = cordic(x=K, y=0, z=math.pi/3, mode="rotation", mu=0)
    print("Results:   X: {} Y: {} Z: {}".format(sol[0], sol[1], sol[2]))
    print("Expected:  X: {} Y: {} Z: {}".format(math.cos(math.pi/3), math.sin(math.pi/3), 0))