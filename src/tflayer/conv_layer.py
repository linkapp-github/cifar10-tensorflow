# -*- coding: utf8 -*-
# author: ronniecao
# time: 20180828
# intro: convolutional layer based on tensorflow.layers
import numpy
import math
import tensorflow as tf
import random


class ConvLayer:
    
    def __init__(self, 
        y_size, x_size, y_stride, x_stride, n_filter, 
        activation='relu', batch_normal=False,
        data_format='channels_first', input_shape=None, prev_layer=None,
        name='conv'):

        # params
        self.y_size = y_size
        self.x_size = x_size
        self.y_stride = y_stride
        self.x_stride = x_stride
        self.n_filter = n_filter
        self.activation = activation
        self.data_format = data_format
        self.batch_normal = batch_normal
        self.name = name
        self.ltype = 'conv'
        self.params = {}
        
        if prev_layer:
            self.prev_layer = prev_layer
            self.input_shape = prev_layer.output_shape
        elif input_shape:
            self.prev_layer = None
            self.input_shape = input_shape
        else:
            raise('ERROR: prev_layer or input_shape cannot be None!')
        
        self.leaky_scale = tf.constant(0.1, dtype=tf.float32)
    
        with tf.name_scope('%s_def' % (self.name)) as scope:
            # 权重矩阵
            numpy.random.seed(0)
            scale = math.sqrt(2.0 / (self.y_size * self.x_size * self.input_shape[2]))
            weight_init_value = scale * numpy.random.normal(size=[
                self.y_size, self.x_size, self.input_shape[2], self.n_filter], loc=0.0, scale=1.0)
            weight_init_value = numpy.array(weight_init_value, dtype='float32')
            bias_init_value = numpy.zeros([self.n_filter], dtype='float32')
            
            self.conv = tf.layers.Conv2D(
                filters=self.n_filter,
                kernel_size=[self.y_size, self.x_size],
                strides=[self.y_stride, self.x_stride],
                padding='SAME',
                data_format=self.data_format,
                activation=None,
                use_bias=not self.batch_normal,
                kernel_initializer=tf.constant_initializer(weight_init_value),
                bias_initializer=tf.constant_initializer(bias_init_value),
                trainable=True,
                name='%s_conv' % (self.name))
            
            if self.batch_normal:
                beta_init_value = numpy.zeros([self.n_filter], dtype='float32')
                gamma_init_value = numpy.ones([self.n_filter], dtype='float32')
                moving_mean_init_value = numpy.zeros([self.n_filter], dtype='float32')
                moving_variance_init_value = numpy.ones([self.n_filter], dtype='float32')
                
                self.bn = tf.layers.BatchNormalization(
                    axis=-1 if self.data_format == 'channels_last' else 1,
                    momentum=0.9,
                    epsilon=1e-5,
                    center=True,
                    scale=True,
                    beta_initializer=tf.constant_initializer(beta_init_value),
                    gamma_initializer=tf.constant_initializer(gamma_init_value),
                    moving_mean_initializer=tf.constant_initializer(moving_mean_init_value),
                    moving_variance_initializer=tf.constant_initializer(moving_variance_init_value),
                    fused=True,
                    trainable=True,
                    name='%s_bn' % (self.name))

        # 打印网络权重、输入、输出信息
        # calculate input_shape and output_shape
        self.output_shape = [
            int(self.input_shape[0]/self.y_stride),
            int(self.input_shape[1]/self.x_stride), 
            self.n_filter]
        print('%-10s\t%-25s\t%-20s\t%-20s' % (
            self.name, 
            '((%d, %d) / (%d, %d) * %d)' % (
                self.y_size, self.x_size, self.y_stride, self.x_stride, self.n_filter),
            '(%d, %d, %d)' % (
                self.input_shape[0], self.input_shape[1], self.input_shape[2]),
            '(%d, %d, %d)' % (
                self.output_shape[0], self.output_shape[1], self.output_shape[2])))
        self.calculation = self.output_shape[0] * self.output_shape[1] * \
            self.output_shape[2] * self.input_shape[2] * self.y_size * self.x_size
        
    def get_output(self, input, is_training=True):
        with tf.name_scope('%s_cal' % (self.name)) as scope:
            # hidden states
            if self.data_format == 'channels_first':
                input = tf.transpose(input, [0,3,1,2])

            self.hidden = self.conv(inputs=input)
            
            # batch normalization 技术
            if self.batch_normal:
                self.hidden = self.bn(self.hidden, training=tf.constant(True))
                
            # activation
            if self.activation == 'relu':
                self.output = tf.nn.relu(self.hidden)
            elif self.activation == 'tanh':
                self.output = tf.nn.tanh(self.hidden)
            elif self.activation == 'leaky_relu':
                self.output = self.leaky_relu(self.hidden)
            elif self.activation == 'sigmoid':
                self.output = tf.nn.sigmoid(self.hidden)
            elif self.activation == 'none':
                self.output = self.hidden
            
            # gradient constraint
            g = tf.get_default_graph()
            with g.gradient_override_map({"Identity": "CustomClipGrad"}):
                self.output = tf.identity(self.output, name="Identity")
        
            if self.data_format == 'channels_first':
                self.output = tf.transpose(self.output, [0,2,3,1])
        
        # 获取params
        if self.batch_normal:
            for tensor in self.conv.weights:
                if 'kernel' in tensor.name:
                    self.params['%s#%s' % (self.name, 'weight')] = tensor
            for tensor in self.bn.weights:
                if 'gamma' in tensor.name:
                    self.params['%s#%s' % (self.name, 'gamma')] = tensor
        else:
            for tensor in self.conv.weights:
                if 'kernel' in tensor.name:
                    self.params['%s#%s' % (self.name, 'weight')] = tensor
        
        return self.output
    
    def leaky_relu(self, data):
        output = tf.maximum(self.leaky_scale * data, data, name='leaky_relu')
        
        return output
    
    @tf.RegisterGradient("CustomClipGrad")
    def _clip_grad(unused_op, grad):
        return tf.clip_by_value(grad, -1, 1)
