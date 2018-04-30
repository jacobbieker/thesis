from keras import backend as K
import h5py
from fact.io import read_h5py
import yaml
import os
import keras
import numpy as np
from keras.models import Sequential
from keras.layers import Dense, Dropout, Activation, Conv1D, Flatten, Reshape, BatchNormalization, Conv2D, MaxPooling2D

architecture = 'intel'

if architecture == 'manjaro':
    base_dir = '/run/media/jacob/WDRed8Tb1'
    thesis_base = '/run/media/jacob/SSD/Development/thesis'
else:
    base_dir = '/projects/sventeklab/jbieker'
    thesis_base = base_dir + '/git-thesis/thesis'

# Hyperparameters

batch_sizes = [512, 16, 256, 64]
gamma_trains = [1]
patch_sizes = [(3, 3), (5, 5)]
dropout_layers = [0.0, 0.9, 0.2, 0.7, 0.5]
num_conv_layers = [0,1,4,3,2,5]
num_dense_layers = [0,1,4,3,2]
num_conv_neurons = [8, 64, 32, 16, 128]
num_dense_neuron = [64, 512, 256, 128]
num_pooling_layers = [0,1]
number_of_training = 800000*(0.6)
number_of_testing = 800000*(0.2)
number_validate = 800000*(0.2)
num_labels = 2

path_mc_images = base_dir + "/FACTSources/Rebinned_5_MC_Phi_Images.h5"
for batch_size in batch_sizes:
    for patch_size in patch_sizes:
        for dropout_layer in dropout_layers:
            for num_conv in num_conv_layers:
                for num_dense in num_dense_layers:
                    for num_pooling_layer in num_pooling_layers:
                        for conv_neurons in num_conv_neurons:
                            for dense_neuron in num_dense_neuron:
                                for gamma_train in gamma_trains:
                                    try:
                                        model_name = base_dir + "/MC_Sep_b" + str(batch_size) +"_p_" + str(patch_size) + "_drop_" + str(dropout_layer) \
                                                     + "_conv_" + str(num_conv) + "_pool_" + str(num_pooling_layer) + "_gamma_" + \
                                                     str(gamma_train) + "_denseN_" + str(dense_neuron) + "_convN_" + str(conv_neurons) + ".h5"
                                        if not os.path.isfile(model_name):
                                            model_checkpoint = keras.callbacks.ModelCheckpoint(model_name, monitor='val_loss', verbose=0,
                                                                                               save_best_only=True, save_weights_only=False, mode='auto', period=1)
                                            early_stop = keras.callbacks.EarlyStopping(monitor='val_loss', min_delta=0, patience=4, verbose=0, mode='auto')
                                            def metaYielder():
                                                with h5py.File(path_mc_images, 'r') as f:
                                                    gam = len(f['GammaImage'])
                                                    had = len(f['Image'])
                                                    sumEvt = gam + had

                                                gamma_anteil = gam/sumEvt
                                                hadron_anteil = had/sumEvt

                                                gamma_count = int(round(number_of_training*gamma_anteil))
                                                hadron_count = int(round(number_of_training*hadron_anteil))

                                                return gamma_anteil, hadron_anteil, gamma_count, hadron_count


                                            with h5py.File(path_mc_images, 'r') as f:
                                                gamma_anteil, hadron_anteil, gamma_count, hadron_count = metaYielder()
                                                # Get some truth data for now, just use Crab images
                                                images = f['GammaImage'][-(gamma_anteil*number_of_testing):-1]
                                                images_false = f['Image'][-(hadron_anteil*number_of_testing):-1]
                                                validating_dataset = np.concatenate([images, images_false], axis=0)
                                                labels = np.array([True] * (len(images)) + [False] * len(images_false))
                                                del images
                                                del images_false
                                                validation_labels = (np.arange(2) == labels[:, None]).astype(np.float32)
                                                y = validating_dataset
                                                y_label = validation_labels
                                                print("Finished getting data")


                                            def batchYielder():
                                                gamma_anteil, hadron_anteil, gamma_count, hadron_count = metaYielder()
                                                with h5py.File(path_mc_images, 'r') as f:
                                                    items = list(f.items())[1][1].shape[0]
                                                    items = items - number_of_testing
                                                    while True:
                                                        # Get some truth data for now, just use Crab images
                                                        batch_num = 0
                                                        # Roughly 5.6 times more simulated Gamma events than proton, so using most of them
                                                        while (hadron_count) * (batch_num + 1) < items:
                                                            images = f['GammaImage'][np.floor((batch_num) * (batch_size * gamma_anteil)):np.floor((batch_num + 1) * (batch_size * gamma_anteil))]
                                                            images_false = f['Image'][np.floor(batch_num * batch_size * hadron_anteil):(batch_num + 1) * batch_size * hadron_anteil]
                                                            validating_dataset = np.concatenate([images, images_false], axis=0)
                                                            labels = np.array([True] * (len(images)) + [False] * len(images_false))
                                                            del images
                                                            del images_false
                                                            validation_labels = (np.arange(2) == labels[:, None]).astype(np.float32)
                                                            x = validating_dataset
                                                            x_label = validation_labels
                                                            # print("Finished getting data")
                                                            batch_num += 1
                                                            yield (x, x_label)


                                            gamma_anteil, hadron_anteil, gamma_count, hadron_count = metaYielder()
                                            # Make the model
                                            model = Sequential()

                                            # Base Conv layer
                                            model.add(Conv2D(conv_neurons, kernel_size=patch_size, strides=(1, 1),
                                                             activation='relu', padding='same',
                                                             input_shape=(75, 75, 1)))

                                            for i in range(num_conv):
                                                model.add(Conv2D(conv_neurons, patch_size, strides=(1, 1), activation='relu', padding='same'))
                                                if num_pooling_layer == 1:
                                                    model.add(MaxPooling2D(pool_size=(2, 2), padding='same'))
                                                model.add(Dropout(dropout_layer))

                                            model.add(Flatten())

                                            # Now do the dense layers
                                            for i in range(num_dense):
                                                model.add(Dense(dense_neuron, activation='relu'))
                                                model.add(Dropout(dropout_layer))

                                            # Final Dense layer
                                            model.add(Dense(num_labels, activation='softmax'))
                                            model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['acc'])
                                            model.fit_generator(generator=batchYielder(), steps_per_epoch=np.floor(((number_of_training / batch_size))), epochs=100,
                                                                verbose=2, validation_data=(y, y_label), callbacks=[early_stop, model_checkpoint])

                                    except Exception as e:
                                        print(e)
                                        pass
