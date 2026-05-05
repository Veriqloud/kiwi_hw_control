import numpy as np, matplotlib.pylab as plt

plt.figure()
for file in ['calib.txt']:
    data = np.loadtxt(file)

    vca = data[:,0]
    p = data[:,1]

    p = p/p.max()

    plt.plot(vca, p)
plt.show()






