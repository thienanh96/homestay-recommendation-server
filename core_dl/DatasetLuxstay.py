import scipy.sparse as sp
import numpy as np
import pandas as pd
import scipy.sparse as sp

# Luxstay_click_detail


class DatasetLuxstay():
    '''
    classdocs
    '''

    def __init__(self):
        self.user_mapping_arr = []
        self.room_mapping_arr = []

        self.dokMatrix = []
        self.trainMatrix = self.load_rating_file_as_matrix('luxstay_train.csv')
        self.testNegatives = self.load_negative_file('luxstay_test_negative.csv')
        test_rating_matrix = self.load_rating_file_test_rating('luxstay_test.csv')
        self.testRatings = self.load_rating_file_as_list(test_rating_matrix)
        print('Check len____________',len(self.testRatings),len(self.testNegatives))
        assert len(self.testRatings) == len(self.testNegatives)
        self.num_users, self.num_items = self.trainMatrix.shape

    def loadHomestayFromCSV(self, filename):
        df = pd.read_csv(filename, sep="\s+")
    
    def load_negative_file(self, filename):
        negativeList = []
        with open(filename, "r") as f:
            line = f.readline()
            while line != None and line != "":
                arr = line.split("\t")
                negatives = []
                for x in arr[1: ]:
                    negatives.append(int(x))
                negativeList.append(negatives)
                line = f.readline()
        return negativeList

    def loadNegative(self, ratingMatrix):
        finalMatrix = []
        for row in ratingMatrix:
            rowMatrix = []
            itemIndex = 0
            limitPerRow = 0
            for col in row:
                if((int(col) == 0) and (limitPerRow <= 98)):
                    rowMatrix.append(itemIndex)
                    limitPerRow += 1
                itemIndex += 1
            finalMatrix.append(rowMatrix)
        return finalMatrix

    def loadMl(seld, filename):
        dfML = pd.read_csv('Data/ml-1m.train.rating',
                           sep="\s+", names=[0, 1, 2, 3])
        dfLS = pd.read_csv('DataLuxstay/' + filename, sep=';')
        userids = []
        roomids = []
        for ir in dfLS.itertuples():
            userid = str(ir[2]).replace('.0', '')
            if(userid == "\\N"):
                # print('Check NAN____',userid)
                continue
            userids.append(userid)
            roomids.append(ir[3])
        newFrame = pd.DataFrame({"user_id": userids, "room_id": roomids})
        newFrame.to_csv('finalLuxstay.csv', sep='\t')

    def load_rating_file_as_matrix(self, filename):
        num_users, num_items, min_items = 0, 0, 1000000000  # init values
        dfData = pd.read_csv(filename, sep="\s+", header=None)
        for ir in dfData.itertuples():
            r, u = int(ir[2]), int(ir[1])
            num_users = max(num_users, u)
            num_items = max(num_items, r)
            min_items = min(num_items, r)
        print('MAX MIN user rooms____: ',num_users,num_items)
        # Construct matrix
        mat = sp.dok_matrix(
            (num_users+1, num_items+1), dtype=np.float32)
        count = 0
        for ir in dfData.itertuples():
            r, u = int(ir[2]), int(ir[1])
            mat[u, r] = mat[u, r] + 1
            count += 1
        self.dokMatrix = np.array(mat.todense())
        return mat
    
    def load_rating_file_test_rating(self, filename):
        num_users, num_items, min_items = 0, 0, 1000000000  # init values
        dfData = pd.read_csv(filename, sep="\s+", header=None)
        for ir in dfData.itertuples():
            r, u = int(ir[2]), int(ir[1])
            num_users = max(num_users, u)
            num_items = max(num_items, r)
            min_items = min(num_items, r)
        print('MAX MIN user rooms: ',num_users,num_items)
        # Construct matrix
        mat = sp.dok_matrix(
            (num_users+1, num_items+1), dtype=np.float32)
        count = 0
        for ir in dfData.itertuples():
            r, u = int(ir[2]), int(ir[1])
            mat[u, r] = mat[u, r] + 1
            count += 1
        return np.array(mat.todense())

    def load_rating_file_as_list(self, ratingMatrix):
        finalMatrix = []
        userIndex = 0
        for row in ratingMatrix:
            itemIndex = 0
            for col in row:
                if(int(col) != 0):
                    finalMatrix.append([userIndex, itemIndex])
                    break
                itemIndex += 1
            userIndex += 1
        print('def load_rating_file_as_list(self, ratingMatrix): ===>length finalMatrix',len(finalMatrix))
        return finalMatrix

    def user_mapping(self):
        dfLS = pd.read_csv('finalLuxstay.csv', sep="\s+")
        user_ids = np.array(dfLS['user_id'])
        user_ids = np.unique(user_ids)
        count = 0
        sttArray = []
        for userid in user_ids:
            sttArray.append(count)
            count += 1
        newFrame = pd.DataFrame({"stt": sttArray, "user_id": user_ids})
        newFrame.to_csv('user_mapping.csv', sep='\t')

    def room_mapping(self):
        dfLS = pd.read_csv('finalLuxstay.csv', sep="\s+")
        room_ids = np.array(dfLS['room_id'])
        room_ids = np.unique(room_ids)
        count = 0
        sttArray = []
        for room_id in room_ids:
            sttArray.append(count)
            count += 1
        newFrame = pd.DataFrame({"stt": sttArray, "room_id": room_ids})
        newFrame.to_csv('room_mapping.csv', sep='\t')

    def loadMapping(self):
        dfUser = pd.read_csv('user_mapping.csv', sep="\s+")
        dfRoom = pd.read_csv('room_mapping.csv', sep="\s+")
        self.user_mapping_arr = np.array(dfUser)
        self.room_mapping_arr = np.array(dfRoom)
        new_users_arr = []
        new_room_arr = []
        dfLs = pd.read_csv('finalLuxstay.csv', sep="\s+")
        for ir in dfLs.itertuples():
            res_room = np.where(self.room_mapping_arr == int(ir[1]))[0][0]
            res_user = np.where(self.user_mapping_arr == int(ir[2]))[0][0]
            new_room_arr.append(res_room)
            new_users_arr.append(res_user)
        newFrame = pd.DataFrame(
            {"user_id": new_users_arr, "room_id": new_room_arr})
        newFrame.to_csv('new_luxstay.csv', sep='\t')


dt = DatasetLuxstay()
