import numpy as np
import argparse
import tensorflow as tf
from keras import backend as K
from keras.models import Sequential
from keras.layers import Dense, Activation, Conv1D, Flatten, Reshape
from keras.layers.noise import AlphaDropout
from keras.utils import to_categorical, Sequence
from keras.regularizers import l2
from keras.optimizers import Adam
from keras.callbacks import TensorBoard

from thesisTools import kerasTools

params={
           'lr': 0.001,
           'conv_dr': 0.,
           'fc_dr': 0.1,
           'batch_size': 128,
           'no_epochs': 1000,
           'steps_per_epoch': 100,
           'dp_prob': 0.5,
           'batch_norm': False,
           'regularize': 0.0,
           'decay': 0.0
       },

config = tf.ConfigProto(gpu_options=tf.GPUOptions(allocator_type='BFC'))

sess = tf.Session(config=config)

K.set_session(sess)

#Define model
model = Sequential()

# Set up regulariser
regularizer = l2(0.0)

model.add(Dense(1024, input_shape=([45,46]), activation='selu', kernel_regularizer=regularizer))
model.add(AlphaDropout(0.1))
model.add(Dense(1024, activation='selu', kernel_regularizer=regularizer))
model.add(AlphaDropout(0.1))
model.add(Dense(1024, activation='selu', kernel_regularizer=regularizer))
model.add(AlphaDropout(0.1))
model.add(Dense(64, activation='selu', kernel_regularizer=regularizer))
model.add(AlphaDropout(0.1))
model.add(Dense(2, activation='softmax'))

# Set up optimizer
optimizer = Adam(lr=0.001)

#Create Model
model.compile(
    optimizer=optimizer,
    loss='categorical_crossentropy',
    metrics=['accuracy', kerasTools.precision, kerasTools.recall, kerasTools.f1, kerasTools.class_balance]
)

# Need to load data
