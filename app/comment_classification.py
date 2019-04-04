import numpy as np
import os
import keras
from keras import regularizers
from keras.callbacks import ModelCheckpoint
from keras.models import Sequential
from keras.layers import Dense, Dropout, LSTM,Bidirectional
import tensorflow as tf
print(tf.__version__)
from gensim.models import Word2Vec
from pyvi import ViTokenizer, ViPosTagger
from keras import backend as K

class BaseTextClassifier(object):
    def train(self, X, y):
        """
        Training using data X, y
        :param X: input feature array
        :param y: label array
        :return:
        """
        pass

    def predict(self, X):
        """
        Predict for input X
        :param X: input feature array
        :return: y as a label array
        """
        pass


def load_synonym_dict(file_path):
    """
    Load synonyms from file and create synonym dictionary
    :param file_path: path to synonym file
    :return: synonym dictionary
    """
    sym_dict = dict()
    with open(file_path, 'r') as fr:
        lines = fr.readlines()
    lines = [ln.strip() for ln in lines if len(ln.strip()) > 0]
    for ln in lines:
        words = ln.split(",")
        words = [w.strip() for w in words]
        for word in words[1:]:
            sym_dict.update({word: words[0]})
    return sym_dict


class KerasTextClassifier(BaseTextClassifier):
    def __init__(self, tokenizer, word2vec, model_path, max_length=20, n_epochs=15, batch_size=32,
                 n_class=2, sym_dict=None):
        """
        Create Text Classifier which based on Keras
        :param tokenizer: tokenizer to do correct word segmentation
        :param word2vec: word2vec dictionary, convert word to vector
        :param model_path: path to save or load model
        :param max_length: max length of a sentence
        :param n_epochs: number of epochs
        :param batch_size: number of samples in each batch
        :param n_class: number of classes
        :param sym_dict: synonym dictionary (optional)
        """
        self.tokenizer = tokenizer
        self.word2vec = word2vec
        self.word_dim = self.word2vec[self.word2vec.index2word[0]].shape[0]
        self.max_length = max_length
        self.n_epochs = n_epochs
        self.batch_size = batch_size
        self.model_path = model_path
        self.n_class = n_class
        self.model = None
        self.sym_dict = sym_dict

    def train(self, X, y):
        """
        Training with data X, y
        :param X: 3D features array, number of samples x max length x word dimension
        :param y: 2D labels array, number of samples x number of class
        :return:
        """
        self.model = self.build_model(input_dim=(X.shape[1], X.shape[2]))
        filepath="models/checkpoint/weights.best.hdf5"
        checkpoint = ModelCheckpoint(filepath, monitor='val_acc', verbose=1, save_best_only=True, mode='max')
        callbacks_list = [checkpoint]
        self.model.fit(X, y, batch_size=self.batch_size, nb_epoch=self.n_epochs,validation_split=0.2,shuffle=True,callbacks=callbacks_list)
        self.model.save_weights(self.model_path)

    def predict(self, X):
        """
        Predict for 3D feature array
        :param X: 3D feature array, converted from string to matrix
        :return: label array y as 2D-array
        """
        if self.model is None:
            self.load_model()
        y = self.model.predict(X)
        return y

    def classify(self, sentences):
        """
        Classify sentences
        :param sentences: input sentences in format of list of strings
        :param label_dict: dictionary of label ids and names
        :return: label array
        """
        # tf.reset_default_graph()
        # K.clear_session()
        X = [sent.strip() for sent in sentences]
        X, _ = self.tokenize_sentences(X)
        X = self.word_embed_sentences(X, max_length=self.max_length)
        y = self.predict(np.array(X))
        return self.label_result(y)

    def load_model(self):
        """
        Load model from file
        :return: None
        """
        self.model = self.build_model((self.max_length, self.word_dim))
        self.model.load_weights(self.model_path)

    def build_model(self, input_dim):
        """
        Build model structure
        :param input_dim: input dimension max_length x word_dim
        :return: Keras model
        """
        model = Sequential()

        model.add(LSTM(64, return_sequences=True, input_shape=input_dim))
        model.add(Dropout(0.5))
        model.add(LSTM(32))
        model.add(Dense(self.n_class, activation="softmax"))

        model.compile(loss='categorical_crossentropy',
                      optimizer=keras.optimizers.Adadelta(),
                      metrics=['accuracy'])
        return model

    def load_data(self, path_list, load_method):
        """
        Load data from list of paths
        :param path_list: list of paths to files or directories
        :param load_method: method to load (from file or from directory)
        :return: 3D-array X and 2D-array y
        """
        X = None
        y = None
        for i, data_path in enumerate(path_list):
            sentences_ = load_method(self,data_path)
            label_vec = [0.0 for _ in range(0, self.n_class)]
            label_vec[i] = 1.0
            labels_ = [label_vec for _ in range(0, len(sentences_))]
            if X is None:
                X = sentences_
                y = labels_
            else:
                X += sentences_
                y += labels_
        X, max_length = self.tokenize_sentences(X)
        X = self.word_embed_sentences(X, max_length=self.max_length)
        return np.array(X), np.array(y)

    def word_embed_sentences(self, sentences, max_length=20):
        """
        Helper method to convert word to vector
        :param sentences: input sentences in list of strings format
        :param max_length: max length of sentence you want to keep, pad more or cut off
        :return: embedded sentences as a 3D-array
        """
        embed_sentences = []
        for sent in sentences:
            embed_sent = []
            for word in sent:
                #lap tung tu trong sent
                if (self.sym_dict is not None) and (word.lower() in self.sym_dict):
                    replace_word = self.sym_dict[word.lower()]
                    embed_sent.append(self.word2vec[replace_word])
                elif word.lower() in self.word2vec:
                    embed_sent.append(self.word2vec[word.lower()])
                else:
                    embed_sent.append(np.zeros(shape=(self.word_dim,), dtype=float))
            if len(embed_sent) > max_length:
                embed_sent = embed_sent[:max_length]
            elif len(embed_sent) < max_length:
                embed_sent = np.concatenate((embed_sent, np.zeros(shape=(max_length - len(embed_sent),
                                                                         self.word_dim), dtype=float)),
                                            axis=0)
            embed_sentences.append(embed_sent)
        return embed_sentences

    def tokenize_sentences(self, sentences):
        """
        Tokenize or word segment sentences
        :param sentences: input sentences
        :return: tokenized sentence
        """
        tokens_list = []
        max_length = -1
        for sent in sentences:
            tokens = self.tokenizer.tokenize(sent).split(' ')
            tokens_list.append(tokens)
            if len(tokens) > max_length:
                max_length = len(tokens)

        return tokens_list, max_length

    @staticmethod
    def load_data_from_file(self,file_path):
        """
        Method to load sentences from file
        :param file_path: path to file
        :return: list of sentences
        """
        with open(file_path, 'r') as fr:
            sentences = fr.readlines()
            sentences = [sent.strip() for sent in sentences if len(sent.strip()) > 0]
        return sentences
    
    @staticmethod
    def load_data_from_dir(self,data_path):
        """
        Load data from directory which contains multiple files
        :param data_path: path to data directory
        :return: 2D-array of sentences
        """
        file_names = os.listdir(data_path)
        sentences = None
        for f_name in file_names:
            file_path = os.path.join(data_path, f_name)
            if f_name.startswith('.') or os.path.isdir(file_path):
                continue
            batch_sentences = self.load_data_from_file(self,file_path)
            if sentences is None:
                sentences = batch_sentences
            else:
                sentences += batch_sentences
        return sentences

    def label_result(self,result):
        if result is None:
            return 0
        positive = float(result[0][0])
        if(positive < 0.45):
            return 2
        if(positive >= 0.45 and positive <= 0.55):
            return 0
        return 1

class BiDirectionalLSTMClassifier(KerasTextClassifier):
    def build_model(self, input_dim):
        """
        Overwrite build model using Bidirectional Layer
        :param input_dim: input dimension
        :return: Keras model
        """
        model = Sequential()

        model.add(Bidirectional(LSTM(32, return_sequences=True), input_shape=input_dim))
        model.add(Dropout(0.1))
        model.add(Bidirectional(LSTM(16)))
        model.add(Dense(self.n_class, activation="softmax"))

        model.compile(loss=keras.losses.categorical_crossentropy,
                      optimizer=keras.optimizers.Adadelta(),
                      metrics=['accuracy'])
        return model

 

word2vec_model = Word2Vec.load('app/model_dl/word2vec-new.model')
tokenizer = ViTokenizer
sym_dict = load_synonym_dict('app/model_dl/synonym.txt')
keras_text_classifier = BiDirectionalLSTMClassifier(tokenizer=tokenizer, word2vec=word2vec_model.wv,
                                                    model_path='app/model_dl/sentiment_model.h5',
                                                    max_length=40, n_epochs=50,
                                                    sym_dict=sym_dict)

keras_text_classifier.load_model()
print('dhs')
graph = tf.get_default_graph()

def classify_comment(comment):
    return keras_text_classifier.classify(comment)


