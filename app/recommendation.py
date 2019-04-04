# import os
# os.environ['KERAS_BACKEND'] = 'theano'
import math
import numpy as np
from keras import initializers
import theano
import theano.tensor as T
import keras
from keras import backend as K
import tensorflow as tf
print(tf.__version__)
# import keras as ks
from keras.optimizers import Adagrad, Adam, SGD, RMSprop
from keras.regularizers import l1, l2
from keras.models import Sequential, Model
from keras.layers.core import Dense, Lambda, Activation
from keras.layers import Embedding, Input, Dense, Multiply, Reshape, Flatten, Dropout, Concatenate,merge
# tf.python.control_flow_ops = tf
# tf.reset_default_graph()
print('runnn')
# print 'Version of Theano: 0.8.0 '
# print 'Version of Tensoflow: 0.12.1 '

num_users = 13941
num_items = 14486
batch_size = 1


def init_normal():
    return initializers.RandomNormal()


def load_model(mf_dim, layers, reg_layers, reg_mf):
    print('check num; ', int(num_users), int(num_items))
    neucf_model = get_model(int(num_users), int(num_items), mf_dim,
                            layers, reg_layers, reg_mf)
    # neucf_model.load_weights('Pretrain/ml-1m_NeuMF_8_[64,32,16,8]_1549202026.h5')
    neucf_model.load_weights(
        'app/model_dl/ml-1m_NeuMF_8_[64,32,16,8]_1553786394.h5')
    return neucf_model


def get_result(predictions):
    pre_array = np.array(predictions).T
    tuples_arr = []
    index = 0
    for idx in pre_array[0]:
        tuples_arr.append((index, idx))
        index = index + 1
    dtype = [('index', int), ('score', float)]
    tuples_arr = np.array(tuples_arr, dtype=dtype)
    tuples_arr = np.sort(tuples_arr, order='score')
    tuples_arr = np.flipud(tuples_arr)
    return tuples_arr

def get_model(num_users, num_items, mf_dim=10, layers=[10], reg_layers=[0], reg_mf=0):
    assert len(layers) == len(reg_layers)
    num_layer = len(layers)  # Number of layers in the MLP
    # Input variables
    user_input = Input(shape=(1,), dtype='int32', name='user_input')
    item_input = Input(shape=(1,), dtype='int32', name='item_input')

    # Embedding layer
    MF_Embedding_User = Embedding(input_dim=num_users, output_dim=mf_dim, name='mf_embedding_user',
                                  embeddings_initializer=initializers.Zeros(), embeddings_regularizer=l2(reg_mf), input_length=1)
    MF_Embedding_User.trainable = False
    MF_Embedding_Item = Embedding(input_dim=num_items, output_dim=mf_dim, name='mf_embedding_item',
                                embeddings_initializer=initializers.Zeros(),embeddings_regularizer=l2(reg_mf), input_length=1)
    MF_Embedding_Item.trainable = False

    MLP_Embedding_User = Embedding(input_dim=num_users, output_dim=int(layers[0]/2), name="mlp_embedding_user",
                                embeddings_initializer=initializers.Zeros(),embeddings_regularizer=l2(reg_layers[0]), input_length=1)
    MLP_Embedding_User.trainable = False
    MLP_Embedding_Item = Embedding(input_dim=num_items, output_dim=int(layers[0]/2), name='mlp_embedding_item',
                                embeddings_initializer=initializers.Zeros(),embeddings_regularizer=l2(reg_layers[0]), input_length=1)
    MLP_Embedding_Item.trainable = False
    # MF part
    mf_user_latent_layer = Flatten()
    mf_user_latent_layer.trainable = False
    mf_user_latent = mf_user_latent_layer(MF_Embedding_User(user_input))
    mf_item_latent_layer = Flatten()
    mf_item_latent_layer.trainable = False
    mf_item_latent = mf_item_latent_layer(MF_Embedding_Item(item_input))
    mf_vector = Multiply()([mf_user_latent, mf_item_latent])
    # MLP part
    mlp_user_latent_layer = Flatten()
    mlp_user_latent_layer.trainable = False
    mlp_user_latent = mlp_user_latent_layer(MLP_Embedding_User(user_input))
    mlp_item_latent_layer = Flatten()
    mlp_item_latent_layer.trainable = False
    mlp_item_latent = mlp_item_latent_layer(MLP_Embedding_Item(item_input))
    # mlp_vector = merge([mlp_user_latent, mlp_item_latent], mode='concat')
    mlp_vector = Concatenate(axis=-1)([mlp_user_latent, mlp_item_latent])
    for idx in range(1, num_layer):
        layer = Dense(output_dim=int(layers[idx]), kernel_regularizer=l2(
            reg_layers[idx]),kernel_initializer=initializers.Zeros(), activation='relu', name="layer%d" % idx)
        layer.trainable = False
        mlp_vector = layer(mlp_vector)
    # Concatenate MF and MLP parts
    #mf_vector = Lambda(lambda x: x * alpha)(mf_vector)
    #mlp_vector = Lambda(lambda x : x * (1-alpha))(mlp_vector)
    predict_vector = Concatenate(axis=-1)([mf_vector, mlp_vector])
    # Final prediction layer
    prediction_layer = Dense(1, activation='sigmoid',
                             kernel_initializer=initializers.Zeros(), name="prediction")
    prediction_layer.trainable = True
    prediction = prediction_layer(predict_vector)
    print('end')
    return Model(input=[user_input, item_input], output=prediction)


def sigmoid(x):
    return 2 / (1 + math.exp(-x)) - 1


def create_data_input(user_id, represent_list):
    user_ids = np.full(len(represent_list), user_id)
    return [user_ids, np.array(represent_list)]

# def make_predictions(model,input_data):
#     predictions = model.predict(input_data,batch_size=1, verbose=0)
#     return predictions


def get_predictions(user_id, represent_list):
    tf.reset_default_graph()
    K.clear_session()

    model = load_model(8, [64, 32, 16, 8], [0, 0, 0, 0], 0)
    print('ok: ')
    model.compile(optimizer=Adam(lr=0.001), loss='binary_crossentropy')
    input_data = create_data_input(user_id, represent_list)
    prediction = model.predict(input_data, batch_size=1, verbose=0)
    return get_result(prediction)


# get_predictions(int(10002), [int(10017), int(10018)])

# get_predictions(123,4485)
# class NeuralNetwork:
#     def __init__(self):
#         self.session = tf.Session()
#         self.graph = tf.get_default_graph()
#         self.model = None
#         # for some reason in a flask app the graph/session needs to be used in the init else it hangs on other threads
#         with self.graph.as_default():
#             with self.session.as_default():
#                 print('ok')

#     def load(self):
#         with self.graph.as_default():
#             with self.session.as_default():
#                 # self.model = load_model(8,[64,32,16,8],[0,0,0,0],0)
#                 self.model = get_model(num_users, num_items,8,[64,32,16,8],[0,0,0,0],0)
#                 self.model.load_weights('app/Pretrain/ml-1m_NeuMF_8_[64,32,16,8]_1553433608.h5')

#     def predict(self,user_id,num_items):
#         with self.graph.as_default():
#             with self.session.as_default():
#                 self.model.compile(optimizer=Adam(lr=0.001), loss='binary_crossentropy')
#                 input_data = create_data_input(user_id,num_items)
#                 prediction = model.predict(input_data,batch_size=1, verbose=0)
#                 print(prediction)


# model = load_model(8,[64,32,16,8],[0,0,0,0],0)
# model.compile(optimizer=Adam(lr=0.001), loss='binary_crossentropy')

# # room_ids = np.arange(4486)
# # user_ids = np.full(4486,123)


# input_data = create_data_input(123,4486)

# # predictions = model.predict([user_ids,room_ids],batch_size=1, verbose=0)
# # res = get_result(predictions)
# # # print(res)
# # print(np.array(res)[0:100])
