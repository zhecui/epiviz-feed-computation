import tensorflow as tf
import keras
import helper_functions
import pandas as pd
import numpy as np
from keras.models import Sequential, load_model
from keras.layers import Dense, Dropout, Activation, Flatten, Conv1D, MaxPooling1D
from keras.layers.core import Reshape

class BaseModel():
    def __init__ (self, measurements, model_path, preprocess_function):
        self.model = load_model(model_path)
        self.measurements = measurements
        self.preprocess_function = preprocess_function

    def preprocess(self, chr, start, end):
        return self.preprocess_function(self.measurements, chr, start, end)

    def predict(self, chr, start, end, params):
            
        X = self.preprocess(chr, start, end)
        return self.model.predict(X) 

    def train(self, train_function, data):
        raise Exception("NotImplementedException")
    
    def buildModel(self, file, filetype):
        raise Exception("NotImplementedException")

    