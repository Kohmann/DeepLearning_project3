import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

from tqdm import tqdm
from sklearn.preprocessing import StandardScaler


def build_model(input_shape=None, load_prev_model=False):
    if isinstance(load_prev_model, str):
        try:
            model = tf.keras.models.load_model(load_prev_model)
            print('Loaded model from file: ' + load_prev_model)

        except:
            print('Error loading model')
            return None
    else:
        model = tf.keras.Sequential()
        model.add(tf.keras.layers.LSTM(units=64, input_shape=input_shape, return_sequences=False))
        #model.add(tf.keras.layers.GRU(units=64, input_shape=input_shape, return_sequences=False))
        model.add(tf.keras.layers.Dense(units=1))
        model.compile(loss=tf.losses.MeanSquaredError(), optimizer='adam', metrics=[tf.metrics.MeanAbsoluteError()])
    return model


from tqdm import tqdm
from sklearn.preprocessing import StandardScaler


class WindowGenerator:
    def __init__(self, train_data, test_data, validation_data=None, target="y", n_input=12 * 24, n_output=1, shift=1,
                 num_predictions=12 * 2, batch_size=32):

        self.train_df = train_data
        self.test_df = test_data
        self.validation_df = validation_data
        self.target_col = target  # string, column name in dataframe
        self.n_features = self.train_df.shape[1] - 1  # minus target
        self.n_input = n_input
        self.n_output = n_output
        self.shift = shift  # for creating lag features
        self.num_predictions = num_predictions
        self.batch_size = batch_size

        self.columns_indices = {col: i for i, col in enumerate(self.train_df.columns)}



    def getInputShape(self):
        return self.n_input, self.n_features

    def normalize(self, data):
        scaler = StandardScaler().fit(self.train_df.values)

        scaled_features = scaler.transform(data.values)
        return scaled_features #pd.DataFrame(scaled_features, index=data.index, columns=data.columns)

    def make_dataset(self, data, batch_size=None):
        if batch_size is None:
            batch_size = self.batch_size

        x_data = self.normalize(data)
        batchIterator = tf.keras.utils.timeseries_dataset_from_array(data=x_data, targets=None,
                                                                     sequence_length=self.n_input + self.shift,
                                                                     batch_size=batch_size, shuffle=False)

        return batchIterator.map(self.split_window)  # splits into features and labels

    def predict_and_plot(self, model, data_raw, start_positions=None, save_plot=False):
        if start_positions is None:
            start_positions = [0]

        for start_pos in start_positions:  # for each given prediction position
            # normalize and split into features and labels
            data = self.make_dataset(data_raw[start_pos:], batch_size=self.num_predictions)

            predictions = []
            first_data = list(data.take(1))[0]  # first batch, but one batch is the whole forcasting window
            sequences = first_data[0].numpy()  # the input data
            scaled_targets = first_data[1].numpy().flatten()

            # first prediction
            sequence = tf.expand_dims(sequences[0], axis=0)
            prediction = model.predict(sequence)[0][0]
            predictions.append(prediction)

            for sequence in tqdm(sequences[1:]):
                # switch out the real y_prev with the predicted y
                sequence[-1, -1] = prediction
                sequence = tf.expand_dims(sequence, axis=0)
                prediction = model.predict(sequence)[0][0]
                predictions.append(prediction)

            predictions = np.array(predictions).flatten()

            history_targets = np.array(sequences[0][-self.n_input // 2:, -1]).flatten()  # history of prev_y's
            predictions = np.concatenate(([history_targets[-1]], predictions))
            scaled_targets = np.concatenate(([history_targets[-1]], scaled_targets))

            len_history = len(history_targets)
            x = range(len_history + self.num_predictions)
            plt.figure(figsize=(12, 6))
            plt.plot(x[:len_history], history_targets, label="history")
            plt.plot(x[len_history - 1:], scaled_targets, label="targets")
            plt.plot(x[len_history - 1:], predictions, label="predictions")
            # plt.plot(targets, label="targets")
            plt.legend()
            if save_plot:
                plt.savefig("prediction_plots/predictions_startpos=" + str(start_pos) + ".png")
                plt.close()
            else:
                plt.show()

    def split_window(self, dataObj):

        samples = dataObj[:, slice(0, self.n_input), slice(0, self.columns_indices[self.target_col])]  # selects sequence length and the relevant features
        labels = dataObj[:, slice(self.n_input, None), :]  # from the end of the sequence, select the target
        labels = labels[:, :, self.columns_indices[self.target_col]]  # select only the y value

        samples.set_shape([None, self.n_input, None])  # reshape to [batch_size, sequence_length, features]
        labels.set_shape([None, self.n_output])  # reshape to [batch_size, feature]

        # print(samples.shape, labels.shape)
        return samples, labels

    def getTrainData(self):
        return self.make_dataset(self.train_df)

    def getTestData(self):
        return self.make_dataset(self.test_df, batch_size=self.num_predictions)

    def getValidationData(self):
        return self.make_dataset(self.validation_df, batch_size=self.num_predictions)


def add_time_features(df):
    # converts time, which is periodically, as a sine/cosine wave with equal periods
    df['start_time'] = pd.to_datetime(df['start_time'])
    df['Minute sine'] = np.sin(2 * np.pi * df['start_time'].dt.minute / 60)
    df['Minute cosine'] = np.cos(2 * np.pi * df['start_time'].dt.minute / 60)
    df['Hour sine'] = np.sin(2 * np.pi * df['start_time'].dt.hour / 24)
    df['Hour cosine'] = np.cos(2 * np.pi * df['start_time'].dt.hour / 24)
    df['Day sine'] = np.sin(2 * np.pi * df['start_time'].dt.day / 365.2524)
    df['Day cosine'] = np.cos(2 * np.pi * df['start_time'].dt.day / 365.2524)
    df['Month sine'] = np.sin(2 * np.pi * df['start_time'].dt.month / 12)
    df['Month cosine'] = np.cos(2 * np.pi * df['start_time'].dt.month / 12)
    df['Week sine'] = np.sin(2 * np.pi * df['start_time'].dt.isocalendar().week / 52)
    df['Week cosine'] = np.cos(2 * np.pi * df['start_time'].dt.isocalendar().week / 52)
    # df['Year sine'] = np.sin(2*np.pi*df['start_time'].dt.year/365.2524)
    # df['Year cosine'] = np.cos(2*np.pi*df['start_time'].dt.year/365.2524)
    return df


def add_lag_features(df, lag):
    df['prev_y_' + str(lag)] = df['y'].shift(lag)
    df.dropna(inplace=True)
    return df


def clean_data(df_train, df_test):
    df_train_min = df_train.y.min()
    df_train_max = df_train.y.max()

    return df_train


def fit_and_plot(model, train_data, test_data, epochs):
    history = model.fit(train_data, epochs=epochs, verbose=1, validation_data=(test_data))

    plt.plot(history.history['loss'], label='train')
    if history.history['val_loss'][-1] / 10 > history.history['loss'][-1]:  # if the losses differ alot, make two plots
        plt.legend()
        plt.show()
    plt.plot(history.history['val_loss'], label='test')
    plt.legend()
    plt.show()
    return model