import subprocess, os, sys, argparse

def DelVar_calcul(min_lat, max_lat):
    Var = max_lat - min_lat + 2
    print("Var:" + str(hex(int(Var))))
    F = 1
    K = 32
    PclockFactor = 4/F
    Del = ((min_lat-1)*PclockFactor) % K
    print("Del:" + str(hex(int(Del))))

def main():
    def lat(args):
        if args.latency is not None:
            min_lat = int(args.latency[0])
            max_lat = int(args.latency[1])
            if (min_lat == 0):
                min_lat = max_lat
                max_lat = 8
            elif (min_lat == 1):
                min_lat = max_lat
                max_lat = 9
        DelVar_calcul(min_lat,max_lat)

    #create top_level parser
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(required=True)

    #create parser for "lat" command
    parser_lat = subparsers.add_parser('lat')
    parser_lat.add_argument("--latency",nargs=2,metavar=('min','max'), help="min, max int [0..7]")
    parser_lat.set_defaults(func=lat)
    args = parser.parse_args()
    args.func(args)

if __name__ =="__main__":
    main()
