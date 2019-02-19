import numpy as np
from keras import initializations
import theano
import theano.tensor as T
import keras
import tensorflow as tf
from keras.optimizers import Adagrad, Adam, SGD, RMSprop
from keras.regularizers import l1, l2, l1l2
from keras.models import Sequential, Model
from keras.layers.core import Dense, Lambda, Activation
from keras.layers import Embedding, Input, Dense, merge, Reshape, Merge, Flatten, Dropout
tf.python.control_flow_ops = tf

print 'Version of Theano: 0.8.0 '
print 'Version of Tensoflow: 0.12.1 '

def init_normal(shape, name=None):
    return initializations.normal(shape, scale=0.01, name=name)


def add_user(num_users, num_items,mf_dim, layers, reg_layers, reg_mf):
    neucf_model = get_model(num_users, num_items,mf_dim, layers, reg_layers, reg_mf)
    # neucf_model.load_weights('Pretrain/ml-1m_NeuMF_8_[64,32,16,8]_1549202026.h5')
    neucf_model.load_weights('Pretrain/NeuMF.h5')
    return neucf_model


def get_model(num_users, num_items, mf_dim=10, layers=[10], reg_layers=[0], reg_mf=0):
    assert len(layers) == len(reg_layers)
    num_layer = len(layers) #Number of layers in the MLP
    # Input variables
    user_input = Input(shape=(1,), dtype='int32', name = 'user_input')
    item_input = Input(shape=(1,), dtype='int32', name = 'item_input')
    
    # Embedding layer
    MF_Embedding_User = Embedding(input_dim = num_users, output_dim = mf_dim, name = 'mf_embedding_user',
                                  init = init_normal, W_regularizer = l2(reg_mf), input_length=1)
    MF_Embedding_User.trainable = False
    MF_Embedding_Item = Embedding(input_dim = num_items, output_dim = mf_dim, name = 'mf_embedding_item',
                                  init = init_normal, W_regularizer = l2(reg_mf), input_length=1)   
    MF_Embedding_Item.trainable = False

    MLP_Embedding_User = Embedding(input_dim = num_users, output_dim = layers[0]/2, name = "mlp_embedding_user",
                                  init = init_normal, W_regularizer = l2(reg_layers[0]), input_length=1)
    MLP_Embedding_User.trainable = False
    MLP_Embedding_Item = Embedding(input_dim = num_items, output_dim = layers[0]/2, name = 'mlp_embedding_item',
                                  init = init_normal, W_regularizer = l2(reg_layers[0]), input_length=1)   
    MLP_Embedding_Item.trainable = False

    # MF part
    mf_user_latent_layer = Flatten()
    mf_user_latent_layer.trainable = False
    mf_user_latent = mf_user_latent_layer(MF_Embedding_User(user_input))
    mf_item_latent_layer = Flatten()
    mf_item_latent_layer.trainable = False
    mf_item_latent = mf_item_latent_layer(MF_Embedding_Item(item_input))
    mf_vector = merge([mf_user_latent, mf_item_latent], mode = 'mul') # element-wise multiply
    
    # MLP part 
    mlp_user_latent_layer = Flatten()
    mlp_user_latent_layer.trainable = False
    mlp_user_latent = mlp_user_latent_layer(MLP_Embedding_User(user_input))
    mlp_item_latent_layer = Flatten()
    mlp_item_latent_layer.trainable = False
    mlp_item_latent = mlp_item_latent_layer(MLP_Embedding_Item(item_input))
    mlp_vector = merge([mlp_user_latent, mlp_item_latent], mode = 'concat')
    for idx in xrange(1, num_layer):
        layer = Dense(layers[idx], W_regularizer= l2(reg_layers[idx]), activation='relu', name="layer%d" %idx)
        layer.trainable = False
        mlp_vector = layer(mlp_vector)

    # Concatenate MF and MLP parts
    #mf_vector = Lambda(lambda x: x * alpha)(mf_vector)
    #mlp_vector = Lambda(lambda x : x * (1-alpha))(mlp_vector)
    predict_vector = merge([mf_vector, mlp_vector], mode = 'concat')
    
    # Final prediction layer
    prediction_layer = Dense(1, activation='sigmoid', init='lecun_uniform', name = "prediction")
    prediction_layer.trainable = True
    prediction = prediction_layer(predict_vector)
    
    model = Model(input=[user_input, item_input], 
                  output=prediction)
    
    return model

num_users = 13941
num_items = 14486
batch_size = 1

model = add_user(num_users, num_items,8,[64,32,16,8],[0,0,0,0],0)
model.compile(optimizer=Adam(lr=0.001), loss='binary_crossentropy')
hist = model.fit([np.array([3942]),np.array([123])],np.array([2]),batch_size=batch_size, nb_epoch=1, verbose=0, shuffle=True) 
# model.save_weights('Pretrain/NeuMF.h5', overwrite=True)
print hist.history
predictions = model.predict([np.array([3942,3942,3942,3942]),np.array([120,121,122,123])],batch_size=1, verbose=0)
print predictions
print model.summary()
print 'End!'
