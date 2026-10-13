def lcs(input):
    with open(input, 'r') as rf:
        data = rf.readlines()  # 读取第一行
        print(data[0])

lcs("data01.fna")
