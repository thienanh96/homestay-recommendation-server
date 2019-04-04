from scipy.spatial import distance
from unidecode import unidecode
import textdistance

# dict cho gia dinh
dict_chogiadinh = [('phuhopvoitrenho', 0),
                   ('dembosung', 1), ('khonghutthuoc', 2)]


# dict tien ich bep
dict_tienichbep = [('bepdien', 0), ('lovisong', 1),
                   ('tulanh', 2), ('bepga', 3)]

# dict hoat dong giai tri
dict_hoatdonggiaitri = [('bbq', 0), ('canhquandep', 1), ('gansangolf', 2),
                        ('beboi', 3), ('huongbien', 5), ('chothucung', 19), ('cauca', 97)]

# dict tien ich phong
dict_tienichphong = [('bancong', 0)]

# dict tien tich chung
dict_tienich = [('wifi', 0), ('tv', 1), ('dieuhoa', 2), ('maygiat', 3), ('daugoi,dauxa', 4), ('giayvesinh', 5), ('giayan', 6), ('nuockhoang', 7),
                ('khantam', 8), ('kemdanhrang', 9), ('xaphongtam', 10), ('thangmay', 72), ('staircase', 218), ('thangbo', 219), ('maysay', 922)]

cities = ['hagiang','laocai','huubang','sonla','hoabinh','thainguyen','haiphong','quangninh','bacninh','hungyen','hanoi','vinhphuc','ninhbinh','thanhhoa','nghean','quangbinh','danang','thuathienhue','quangnam','quangngai','binhdinh','gialai','phuyen','daklak','daknong','lamdong','ninhthuan','binhthuan','khanhhoa','vungtau','bariavungtau','tiengiang','vinhlong','hochiminh','tayninh','longan','kiengiang','cantho','bangkok','chuacapnhat','thailand','maidich']

def similarity_by_fields(first_homestay, second_homestay):
    index = 0
    similarity = []
    try:
        for key, value in first_homestay.items():
            if index == 0:
                score = get_price_similarity(value, second_homestay[key])
                similarity.append(score)
            elif index == 1:
                score = get_cities_similarity(value, second_homestay[key])
                similarity.append(score)
            elif index == 2:
                score = 1 if value == second_homestay[key] else 0
                similarity.append(score)
            else:
                score = 0
                if all(i == 0 for i in value) or all(i == 0 for i in second_homestay[key]): 
                    score = 0
                else:
                    score = 1- distance.cosine(value, second_homestay[key])
                similarity.append(score)
            index = index + 1
    except RuntimeWarning as e:
        print('loii: ',e)
    # dist_cos = distance.cosine(similarity, [1,1,1,1,1,1,1,1,1,1],[2,4,5,2,2,2,2,2,2,2])
    # return 1 - distance.cosine(similarity, [1,1,1,1,1,1,1,1,1,1],[2,4,5,2,2,2,2,2,2,2])
    return 1 - distance.cosine(similarity, [1,1,1,1,1,1,1,1,1,1],[2,4,5,2,2,2,2,2,2,2])


def get_cities_similarity(city_1,city_2):
    index=0
    index1 = 0
    index2 = 0
    for city in cities:
        if(city == city_1):
            index1 = index
        elif city == city_2:
            index2 = index
        index = index + 1
    return  1 - (abs(index1 - index2)/len(cities))

def get_price_similarity(price_1,price_2):
    return  1 - (abs(price_1 - price_2)/max(price_1,price_2))

def convert_to_text(arr):
    text = ''
    for el in arr:
        text = text + ',' + el
    return text[1:]

def check_includes(arr, el):
    index = 0
    for ell in arr:
        if ell[0] == el:
            return (True, index)
        index = index + 1
    return (False,)


def create_array(length):
    final = []
    for i in range(length):
        final.append(0)
    return final


def adjust_arr(arr):
    final = []
    for el in arr:
        final.append(unidecode(el).replace(' ', '').lower())
    return final

def embed_to_vector(homestay):
    field_names = homestay['amenities']['data']
    main_price = 0
    try:
        main_price = int(homestay['main_price'])
    except ValueError as e:
        main_price = 0
    vector = {
        'gia': main_price,  # 2
        'city': unidecode(homestay['city']).replace(' ', '').lower(),  # 3
        # 2
        'district': unidecode(homestay['district']).replace(' ', '').lower(),
        'phongngu': None,
        'phongtam': None,
        'chogiadinh': create_array(len(dict_chogiadinh)),
        'tienichbep': create_array(len(dict_tienichbep)),
        'hoatdonggiaitri': create_array(len(dict_hoatdonggiaitri)),
        'tienichphong': create_array(len(dict_tienichphong)),
        'tienich': create_array(len(dict_tienich))
    }
    for field_name in field_names:
        for key, value in field_name.items():
            key = unidecode(key).replace(' ', '').lower()
            value = adjust_arr(value)
            if((key == 'phongngu')):
                intData = []
                try:
                    max_tourist = int(value[0].replace(
                        'toida', '').replace('khach', ''))
                except ValueError as e:
                    max_tourist = 0
                intData.append(max_tourist)
                try:
                    bedrooms = int(value[1].replace('phongngu', ''))
                except ValueError as e:
                    bedrooms = 0
                intData.append(bedrooms)
                try:
                    bed = int(value[2].replace('giuong', ''))
                except ValueError as e:
                    bed = 0
                intData.append(bed)
                vector['phongngu'] = intData
                continue
            if(key == 'phongtam'):
                phongtam = 0
                try:
                    phongtam = int(value[0].replace('phongtam', ''))
                except ValueError as e:
                    phongtam = 0
                vector['phongtam'] = [phongtam]
                continue
            picked_dict = []
            if key == 'chogiadinh':
                picked_dict = dict_chogiadinh
            if key == 'tienichbep':
                picked_dict = dict_tienichbep
            if key == 'hoatdonggiaitri':
                picked_dict = dict_hoatdonggiaitri
            if key == 'tienichphong':
                picked_dict = dict_tienichphong
            if key == 'tienich':
                picked_dict = dict_tienich
            for val in value:
                check_dt = check_includes(picked_dict, val)
            if(check_dt[0] == True):
                vector[key][check_dt[1]] = 1
    return (vector,homestay['homestay_id'])

def get_score(vector_1,vector_2):
    si_vector = similarity_by_fields(vector_1[0], vector_2[0]) 
    return "("+str(vector_1[1])+","+str(vector_2[1])+","+str(si_vector)+")"