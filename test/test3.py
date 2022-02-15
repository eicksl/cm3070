import numpy as np

arr = np.array([
    [
        [1, 2, 3], [1, 2, 3]
    ],
    [
        [1, 2, 3], [1, 3, 3]
    ],
    [
        [1, 2, 3], [1, 2, 3]
    ]
])

#res = np.mean(np.mean(arr, axis=0), axis=0)
#print(res)

arr2D = np.array([[11 ,12, 13, 14],
                  [21, 22, 23, 24],
                  [31, 32, 33, 34]])

arr2D = np.delete(arr2D, np.s_[1:3], axis=1)
print(arr2D)
