import tensorflow as tf
import math


class convLayer(object):
    def __init__(self, name, input_size, filter_dimension, stride_length, activation_function, initializer, regularization_coefficient):
        self.name = name
        self.filter_dimension = filter_dimension
        self.__stride_length = stride_length
        self.__activation_function = activation_function
        self.__initializer = initializer
        self.input_size = input_size
        self.output_size = input_size
        self.regularization_coefficient = regularization_coefficient

        padding = 2*(math.floor(filter_dimension[0] / 2))
        self.output_size[1] = int((self.output_size[1] - filter_dimension[0] + padding) / stride_length + 1)
        padding = 2 * (math.floor(filter_dimension[1] / 2))
        self.output_size[2] = int((self.output_size[2] - filter_dimension[1] + padding) / stride_length + 1)
        self.output_size[-1] = filter_dimension[-1]

    def add_to_graph(self):
        if self.__initializer == 'xavier':
            self.weights = tf.get_variable(self.name + '_weights',
                                           shape=self.filter_dimension,
                                           initializer=tf.contrib.layers.xavier_initializer_conv2d())
        else:
            self.weights = tf.get_variable(self.name + '_weights',
                                           shape=self.filter_dimension,
                                           initializer=tf.truncated_normal_initializer(stddev=5e-2),
                                           dtype=tf.float32)

        self.biases = tf.get_variable(self.name + '_bias',
                                      [self.filter_dimension[-1]],
                                      initializer=tf.constant_initializer(0.1),
                                      dtype=tf.float32)

    def forward_pass(self, x, deterministic):
        # For convention, just use a symmetrical stride with same padding
        activations = tf.nn.conv2d(x, self.weights,
                                   strides=[1, self.__stride_length, self.__stride_length, 1],
                                   padding='SAME')

        activations = tf.nn.bias_add(activations, self.biases)

        # Apply a non-linearity specified by the user
        if self.__activation_function == 'relu':
            activations = tf.nn.relu(activations)
        elif self.__activation_function == 'tanh':
            activations = tf.tanh(activations)

        self.activations = activations


        if activations.shape[-1] == 1:
            return tf.squeeze(activations)
        else:
            return activations

class upsampleLayer(object):
    def __init__(self, name, input_size, filter_size, num_filters, upscale_factor,
                 activation_function, batch_multiplier, initializer, regularization_coefficient):
        self.name = name
        self.activation_function = activation_function
        self.initializer = initializer
        self.input_size = input_size
        self.strides = [1, upscale_factor, upscale_factor, 1]
        self.upscale_factor = upscale_factor
        self.batch_multiplier = batch_multiplier
        self.regularization_coefficient = regularization_coefficient

        # if upscale_factor is an int then height and width are scaled the same
        if isinstance(upscale_factor, int):
            self.strides = [1, upscale_factor, upscale_factor, 1]
            h = self.input_size[1] * upscale_factor
            w = self.input_size[2] * upscale_factor
        else: # otherwise scaled individually
            self.strides = [1, upscale_factor[0], upscale_factor[1], 1]
            h = self.input_size[1] * upscale_factor[0]
            w = self.input_size[2] * upscale_factor[1]

        # upsampling will have the same batch size self.input_size[0],
        # and will preserve the number of filters self.input_size[-1], (NHWC)
        self.output_size = [self.input_size[0], h, w, self.input_size[-1]]

        # the shape needed to initialize weights is based on
        # filter_height x filter_width x input_depth x output_depth
        self.weights_shape = [filter_size, filter_size, input_size[-1], num_filters]

    def add_to_graph(self):
        if self.initializer == 'xavier':
            self.weights = tf.get_variable(self.name + '_weights',
                                           shape=self.weights_shape,
                                           initializer=tf.contrib.layers.xavier_initializer_conv2d())
        else:
            self.weights = tf.get_variable(self.name + '_weights',
                                           shape=self.weights_shape,
                                           initializer=tf.truncated_normal_initializer(stddev=5e-2),
                                           dtype=tf.float32)

        self.biases = tf.get_variable(self.name + '_bias',
                                      [self.weights_shape[-1]],
                                      initializer=tf.constant_initializer(0.1),
                                      dtype=tf.float32)

    def forward_pass(self, x, deterministic):
        # upsampling will have the same batch size (first dimension of x),
        # and will preserve the number of filters (self.input_size[-1]), (this is NHWC)
        dyn_input_shape = tf.shape(x)
        batch_size = dyn_input_shape[0]
        h = dyn_input_shape[1] * self.upscale_factor
        w = dyn_input_shape[2] * self.upscale_factor
        output_shape = tf.stack([batch_size, h, w, self.weights_shape[-1]])

        activations = tf.nn.conv2d_transpose(x, self.weights, output_shape=output_shape,
                                             strides=self.strides, padding='SAME')
        activations = tf.nn.bias_add(activations, self.biases)

        # Apply a non-linearity specified by the user
        if self.activation_function == 'relu':
            activations = tf.nn.relu(activations)
        elif self.activation_function == 'tanh':
            activations = tf.tanh(activations)

        self.activations = activations

        if activations.shape[-1] == 1:
            return tf.squeeze(activations)
        else:
            return activations


class poolingLayer(object):
    def __init__(self, input_size, kernel_size, stride_length, pooling_type='max'):
        self.__kernel_size = kernel_size
        self.__stride_length = stride_length
        self.input_size = input_size
        self.pooling_type = pooling_type

        # The pooling operation will reduce the width and height dimensions
        self.output_size = self.input_size
        filter_size_even = (kernel_size % 2 == 0)

        if filter_size_even:
            self.output_size[1] = int(math.floor((self.output_size[1] - kernel_size) / stride_length + 1))
            self.output_size[2] = int(math.floor((self.output_size[2] - kernel_size) / stride_length + 1))
        else:
            self.output_size[1] = int(math.floor((self.output_size[1]-kernel_size)/stride_length + 1) + 1)
            self.output_size[2] = int(math.floor((self.output_size[2]-kernel_size)/stride_length + 1) + 1)

    def forward_pass(self, x, deterministic):
        if self.pooling_type == 'max':
            return tf.nn.max_pool(x,
                                  ksize=[1, self.__kernel_size, self.__kernel_size, 1],
                                  strides=[1, self.__stride_length, self.__stride_length, 1],
                                  padding='SAME')
        elif self.pooling_type == 'avg':
            return tf.nn.avg_pool(x,
                                  ksize=[1, self.__kernel_size, self.__kernel_size, 1],
                                  strides=[1, self.__stride_length, self.__stride_length, 1],
                                  padding='SAME')


class fullyConnectedLayer(object):
    def __init__(self, name, input_size, output_size, reshape, batch_size, activation_function, initializer, regularization_coefficient):
        self.name = name
        self.input_size = input_size
        self.output_size = output_size
        self.__reshape = reshape
        self.__batch_size = batch_size
        self.__activation_function = activation_function
        self.__initializer = initializer
        self.regularization_coefficient = regularization_coefficient

    def add_to_graph(self):
        # compute the vectorized size for weights if we will need to reshape it
        if self.__reshape:
            vec_size = self.input_size[1] * self.input_size[2] * self.input_size[3]
        else:
            vec_size = self.input_size

        if self.__initializer == 'xavier':
            self.weights = tf.get_variable(self.name + '_weights', shape=[vec_size, self.output_size],
                                           initializer=tf.contrib.layers.xavier_initializer())
        else:
            self.weights = tf.get_variable(self.name + '_weights',
                                           shape=[vec_size, self.output_size],
                                           initializer=tf.truncated_normal_initializer(stddev=math.sqrt(2.0/self.output_size)),
                                           dtype=tf.float32)

        self.biases = tf.get_variable(self.name + '_bias',
                                      [self.output_size],
                                      initializer=tf.constant_initializer(0.1),
                                      dtype=tf.float32)

    def forward_pass(self, x, deterministic):
        # Reshape into a column vector if necessary
        if self.__reshape is True:
            x = tf.reshape(x, [self.__batch_size, -1])

        activations = tf.matmul(x, self.weights)
        activations = tf.add(activations, self.biases)

        # Apply a non-linearity specified by the user
        if self.__activation_function == 'relu':
            activations = tf.nn.relu(activations)
        elif self.__activation_function == 'tanh':
            activations = tf.tanh(activations)

        self.activations = activations

        return activations


class inputLayer(object):
    """An object representing the input layer so it can give information about input size to the next layer"""
    def __init__(self, input_size):
        self.input_size = input_size
        self.output_size = input_size

    def forward_pass(self, x, deterministic):
        return x


class normLayer(object):
    """Layer which performs local response normalization"""
    def __init__(self, input_size):
        self.input_size = input_size
        self.output_size = input_size

    def forward_pass(self, x, deterministic):
        x = tf.nn.lrn(x)
        return x


class dropoutLayer(object):
    """Layer which performs dropout"""
    def __init__(self, input_size, p):
        self.input_size = input_size
        self.output_size = input_size
        self.p = p

    def forward_pass(self, x, deterministic):
        if deterministic:
            return x
        else:
            return tf.nn.dropout(x, self.p)


class moderationLayer(object):
    """Layer for fusing moderating data into the input vector"""
    def __init__(self, input_size, feature_size, reshape, batch_size):
        self.input_size = input_size
        self.__reshape = reshape
        self.__batch_size = batch_size

        # compute the vectorized size for weights if we will need to reshape it
        if reshape:
            vec_size = input_size[1] * input_size[2] * input_size[3]
        else:
            vec_size = input_size

        self.output_size = vec_size + feature_size

    def forward_pass(self, x, deterministic, features):
        # Reshape into a column vector if necessary
        if self.__reshape is True:
            x = tf.reshape(x, [self.__batch_size, -1])

        # Append the moderating features onto the vector
        x = tf.concat([x, features], axis=1)

        return x


class batchNormLayer(object):
    """Batch normalization layer"""
    __epsilon = 1e-3
    __decay = 0.9

    def __init__(self, name, input_size):
        self.input_size = input_size
        self.output_size = input_size
        self.name = name

    def add_to_graph(self):
        if isinstance(self.output_size, (list,)):
            shape = self.output_size
        else:
            shape = [self.output_size]

        zeros = tf.constant_initializer(0.0)
        ones = tf.constant_initializer(1.0)

        self.__offset = tf.get_variable(self.name+'_offset', shape=shape, initializer=zeros, trainable=True)
        self.__scale = tf.get_variable(self.name+'_scale', shape=shape, initializer=ones, trainable=True)

        self.__test_mean = tf.get_variable(self.name+'_pop_mean', shape=shape, initializer=zeros)
        self.__test_var = tf.get_variable(self.name+'_pop_var', shape=shape, initializer=ones)

    def forward_pass(self, x, deterministic):
        mean, var = tf.nn.moments(x, axes=[0])

        if deterministic:
            mean2 = tf.assign(self.__test_mean, self.__test_mean * self.__decay + mean * (1 - self.__decay))
            var2 = tf.assign(self.__test_var, self.__test_var * self.__decay + var * (1 - self.__decay))
        else:
            mean2, var2 = mean, var

        x = tf.nn.batch_normalization(x, mean2, var2, self.__offset, self.__scale, self.__epsilon, name=self.name+'_batchnorm')

        return x
