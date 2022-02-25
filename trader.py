import numpy as np
from tensorflow import keras
import tensorflow as tf
import os
import shutil
import datetime
import pyarrow.feather as feather
import pandas as pd
import activations
import copy
from tempfile import gettempdir

INPUT_NODES = 6 * 50 * 15
OUTPUT_NODES = 3
CHANGE_RATE = 0.035
HIDDEN_NODES = [432, 36]
FEE = 0.001

physical_devices = tf.config.list_physical_devices('GPU') 
tf.config.experimental.set_memory_growth(physical_devices[0], True)

main_path_data = os.path.join("E:\\", "Binance", "data2")

def mutate_arr(arr, mr, cr):
    column = arr.shape[0]

    try:
        rows = arr.shape[1]
    except IndexError:
        rows = 0
    
    change = np.random.rand(column, max(rows, 1))
    random = np.random.normal(arr, 0.08)

    return np.where(change<mr, random, arr)

class Brain:
    
    def __init__(self, symbol, mutation_rate, model=None):
        self.brain_path = os.path.join(main_path_data, 'neat', symbol)
        self.symbol = symbol
        self.mutation_rate = mutation_rate

        if model is None:
            if os.path.exists(self.brain_path):
                self.model = self.loadModel()
                self.model_loaded = True
            else:
                self.model = self.createModel()
                self.model_loaded = False
        else:
            self.model = model
            self.model_loaded = True

    def storeModel(self):
        if os.path.exists(self.brain_path):
            shutil.rmtree(self.brain_path)
        
        os.makedirs(self.brain_path)
        self.model.save(self.brain_path)

    def loadModel(self):
        return tf.keras.models.load_model(self.brain_path)
        
    def createHiddenLayers(self):
        layers = []

        for nodes in HIDDEN_NODES:
            layers.append(keras.layers.Dense(nodes, activation='tanh'))
        
        return layers
    
    def createModel(self):
        layers = [keras.layers.InputLayer(input_shape=(INPUT_NODES,))]
        layers = layers + self.createHiddenLayers()
        layers.append(keras.layers.Dense(OUTPUT_NODES, activation='softmax'))

        model = keras.Sequential(layers)

        return model
    
    def mutate(self):
        weights = []

        for layer in self.model.get_weights():
            weights.append(mutate_arr(layer, self.mutation_rate, CHANGE_RATE))
        
        self.model.set_weights(weights)
    
    def clone(self):
        modelCopy = tf.keras.models.clone_model(self.model)
        modelCopy.set_weights(self.model.get_weights())
        return Brain(self.symbol, self.mutation_rate, modelCopy)

    def predict(self, data):
        return self.model.predict(data)[0]

class BrainOwn:
    def __init__(self, hidden_layers, mutation_rate, symbol):
        self.symbol = symbol
        self.brain_path = os.path.join(main_path_data, 'neat_own', symbol, f'{hidden_layers}_layers')
        self.mutation_rate = mutation_rate
        self.generator = np.random.default_rng(int(datetime.datetime.now().timestamp()))
        self.layers = hidden_layers

        
        if not os.path.exists(self.brain_path):
            self.hidden_nodes = self.loadHiddenNodes()
            self.weights = self.loadWeights()
            self.biases = self.loadBiases()
            self.model_loaded = False
        else:
            self.hidden_nodes = None
            self.weights = None
            self.biases = None
            self.loadModel()
            self.model_loaded = True
            
        self.len_weights = len(self.weights)
        self.activation = self.loadActivation()
    
    def loadActivation(self):
        return np.vectorize(activations.ActivationFunctionSet().get("tanh"))

    def loadHiddenNodes(self):
        nodes = []
        for i in range(1, self.layers+1):
            nodes.append(self.generator.integers(INPUT_NODES/2, INPUT_NODES, 1)[0])
        return np.array(nodes)
    
    def loadWeights(self):
        weights = [self.generator.uniform(-1, 1, (self.hidden_nodes[0], INPUT_NODES))]
        for i in range(self.layers):
            if i > 0:
                weights.append(self.generator.uniform(-1, 1, (self.hidden_nodes[i], self.hidden_nodes[i-1])))
        
        weights.append(self.generator.uniform(-1, 1, (OUTPUT_NODES, self.hidden_nodes[-1])))

        return weights
    
    def loadBiases(self):
        biases = []

        for i in range(self.layers):
            biases.append(self.generator.uniform(-1, 1, (self.hidden_nodes[i], 1)))
        
        biases.append(self.generator.uniform(-1, 1, (OUTPUT_NODES, 1)))

        return biases
    
    def storeModel(self):
        if os.path.isdir(self.brain_path):
            shutil.rmtree(self.brain_path)
        
        os.makedirs(self.brain_path)

        file_path_nodes = os.path.join(self.brain_path, 'hidden.feather')

        for i in range(len(self.weights)):
            file_path_weights = os.path.join(self.brain_path, f'weights{i}.feather')
            file_path_biases = os.path.join(self.brain_path, f'biases{i}.feather')
            feather.write_feather(pd.DataFrame(self.weights[i]), file_path_weights)
            feather.write_feather(pd.DataFrame(self.biases[i]), file_path_biases)
        
        feather.write_feather(pd.DataFrame(self.hidden_nodes), file_path_nodes)
    
    def tempStore(self, idx):
        file_path = os.path.join(main_path_data, 'temp', str(idx))

        if not os.path.exists(file_path):
            os.makedirs(file_path)

        for i in range(len(self.weights)):
            file_path_weights = os.path.join(file_path, f'weights{i}.feather')
            file_path_biases = os.path.join(file_path, f'biases{i}.feather')
            feather.write_feather(pd.DataFrame(self.weights[i]), file_path_weights, compression='lz4')
            feather.write_feather(pd.DataFrame(self.biases[i]), file_path_biases, compression='lz4')
        
        del self.weights
        del self.biases
    
    def tempLoad(self, idx):
        file_path = os.path.join(main_path_data, 'temp')
        weights = []
        biases = []

        for i in range(self.len_weights):
            file_path_weights = os.path.join(file_path, str(idx), f'weights{i}.feather')
            file_path_biases = os.path.join(file_path, str(idx), f'biases{i}.feather')
            weights.append(feather.read_feather(file_path_weights).to_numpy())
            biases.append(feather.read_feather(file_path_biases).to_numpy())
        
        shutil.rmtree(os.path.dirname(file_path_weights))
        
        self.weights = weights
        self.biases = biases
        
    def predict(self, data:np.ndarray):
        
        if data.ndim == 1:
            data = np.transpose(data[np.newaxis])
        
        for i in range(len(self.weights)):
            data = np.matmul(self.weights[i], data)
            data = data + self.biases[i]
            data = self.activation(data)
        
        return data

    def clone(self):
        return copy.deepcopy(self)
    
    def mutate(self):
        for i in range(len(self.weights)):
            self.weights[i] = mutate_arr(self.weights[i], self.mutation_rate, 0)
            self.biases[i] = mutate_arr(self.biases[i], self.mutation_rate, 0)
    
    def loadModel(self):
        file_path_nodes = os.path.join(self.brain_path, 'hidden.feather')
        hidden_nodes_df: pd.DataFrame = feather.read_feather(file_path_nodes)
        self.hidden_nodes = np.transpose(hidden_nodes_df.to_numpy().astype(int))[0, :]
        self.weights = []
        self.biases = []

        for i in range(self.layers + 1):
            file_path_weights = os.path.join(self.brain_path, f'weights{i}.feather')
            file_path_biases = os.path.join(self.brain_path, f'biases{i}.feather')
            weights_df: pd.DataFrame = feather.read_feather(file_path_weights)
            biases_df: pd.DataFrame = feather.read_feather(file_path_biases)

            self.weights.append(weights_df.to_numpy())
            self.biases.append(biases_df.to_numpy())
        
class Trader:

    def __init__(self, idx, mutation_rate, symbol, layers, brain=None):
        self.idx = idx
        self.mutation_rate = mutation_rate
        self.symbol = symbol
        self.layers = layers
        if brain is None:
            self.brain = BrainOwn(layers, mutation_rate, symbol)
        else:
            self.brain = brain

        self.bought = False
        self.bought_value = 0
        self.profit = 0
        self.prob = 0
        self.lastProfit = float('inf')
        self.lastCounter = 0

        self.counter = 0
        self.counterHolding = 0

        self.countBuy = 0
        self.countSell = 0
        self.countHold = 0

        self.tradesProfit = 0
        self.tradesLoss = 0
        self.tradesCounter = 0

        self.fitness = 0
    
    def think(self, data):
        self.counter += 1
        
        if self.bought:
            self.counterHolding += 1
        
        # input_data = tf.convert_to_tensor(data)
        output = self.brain.predict(data)

        # value = data[0, 0]
        value = data[0]

        choice = np.argmax(output)

        if choice == 0:
            self.countBuy += 1
            self.buy(value)
        elif choice == 1:
            self.countSell += 1
            self.sell(value)
        else:
            self.countHold += 1
            pass

        self.fitness += self.profit
    
    def clone_mutate(self, idx):
        brain = self.brain.clone()
        brain.mutate()
        return Trader(idx, self.mutation_rate, self.symbol, self.layers, brain=brain)
    
    def mutate(self):
        self.brain.mutate()
    
    def store(self):
        print(f'Storing trader {self.idx} with fitness: {self.fitness}')
        self.brain.storeModel()
    
    def tempStore(self):
        self.brain.tempStore(self.idx)
    
    def tempLoad(self):
        self.brain.tempLoad(self.idx)

    def buy(self, value):
        if not self.bought:
            self.tradesCounter += 1
            self.bought = True
            self.bought_value = value
    
    def sell(self, value):
        if self.bought:
            self.bought = False
            new_profit = (((value * (1 - FEE)**2) - self.bought_value)) / self.bought_value
            if new_profit > 0:
                self.tradesProfit += 1
            else:
                self.tradesLoss += 1
            
            self.profit = (self.profit + 1) * (new_profit + 1) - 1


