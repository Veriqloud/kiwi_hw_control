import math
from math import log as ln# on francise le log en log neperien ln
from math import exp
#---coefficients de Steinhart-Hart---#
A=1.129241e-3
B=2.341077e-4
C=8.775468e-8
T=29+273.15
#---------------------------------------------------#
x=(1/C)*(A-1/T)
y=((B/3/C)**3+(x/2)**2)**0.5
Tc= T-273.15 # temperature en degres Celsius
R= exp(pow((y-(x/2)),1/3.0)-(pow((y+(x/2)),1/3.0)))
#print(x,y)
#print(A,B,C)
print(R,Tc)
