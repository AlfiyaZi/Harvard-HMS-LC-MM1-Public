# Copyright 2015 The TensorFlow Authors. All Rights Reserved.
# + 2017 YG

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

# YG 2017

""" Trainer, with model heavily adapted from LeNet-5-like model
    (mnist convolutional tutorial) """

import argparse
import gzip
import os
import sys
import time
import itertools

import numpy
import tensorflow as tf

from helpers.input_data import Dataset, batch as batcher
from helpers.tensorboard import variable_summaries
from nnets.lenet5like_map import model, fc1_weights, fc1_biases, fc2_biases, fc2_weights

WORK_DIRECTORY = 'data'
IMAGE_SIZE = 512
TARGET_SIZE = 64
PIXEL_DEPTH = 2200
NUM_CHANNELS = 3    # 3 slices stacked for features
NUM_LABELS = 10
VALIDATION_SIZE = 5000  # Size of the validation set.
BATCH_SIZE = 4
NUM_EPOCHS = 100
EVAL_BATCH_SIZE = 64
DECODING_BATCH_SIZE = 1
EVAL_FREQUENCY = 10  # Number of steps between evaluations.


FLAGS = None


def data_type():
  """Return the type of the activations, weights, and placeholder variables."""
  #if FLAGS.use_fp16:
  #  return tf.float16
  #else:
  return tf.float32



def error_rate(predictions, labels):
  """Return the error rate based on dense predictions and sparse labels."""
  return 100.0 - (
      100.0 *
      numpy.sum(numpy.argmax(predictions, 1) == labels) /
      predictions.shape[0])



def main(_):

  # Data provider.
  train_data = Dataset("/home/gerey/hms_lung/data/example_extracted")
  #train_data = Dataset("/home/gerey/hms_lung/data/example_extracted_sample")

  num_epochs = NUM_EPOCHS
  train_size = train_data.nb_scans() * 100  # Approximation, nevermind

  # This is where training samples and labels are fed to the graph.
  # These placeholder nodes will be fed a batch of training data at each
  # training step using the {feed_dict} argument to the Run() call below.
  train_data_node = tf.placeholder(
      data_type(),
      shape=(BATCH_SIZE, IMAGE_SIZE, IMAGE_SIZE, NUM_CHANNELS),
      name="training_samples")
  train_labels_node = tf.placeholder(
      data_type(),
      shape=(BATCH_SIZE, TARGET_SIZE, TARGET_SIZE),
      name="training_labels")
  variable_summaries(train_data_node,"input")
  variable_summaries(train_labels_node,"target")
  #eval_data = tf.placeholder(
  #    data_type(),
  #    shape=(EVAL_BATCH_SIZE, IMAGE_SIZE, IMAGE_SIZE, NUM_CHANNELS))
  #decode_node = tf.placeholder(
  #    data_type(),
  #    shape=(DECODING_BATCH_SIZE, IMAGE_SIZE, IMAGE_SIZE, NUM_CHANNELS),
  #    name="ygy_input_decoding")

  # Training computation: l2 loss.
  # TODO: Better loss function!
  pred = model(train_data_node, True)
  #loss = tf.reduce_mean(tf.nn.l2_loss(logits, train_labels_node))
  loss = tf.reduce_mean(tf.square(pred - train_labels_node), name="loss")

  # L2 regularization for the fully connected parameters.
  regularizers = (tf.nn.l2_loss(fc1_weights) + tf.nn.l2_loss(fc1_biases) +
                  tf.nn.l2_loss(fc2_weights) + tf.nn.l2_loss(fc2_biases))
  # Add the regularization term to the loss.
  loss += 5e-7 * regularizers

  # Optimizer: set up a variable that's incremented once per batch and
  # controls the learning rate decay.
  batch = tf.Variable(0, dtype=data_type())
  # Decay once per epoch, using an exponential schedule starting at 0.01.
  learning_rate = tf.train.exponential_decay(
      0.01,                # Base learning rate.
      batch * BATCH_SIZE,  # Current index into the dataset.
      train_size,          # Decay step.
      0.95,                # Decay rate.
      staircase=True)
  # Use simple momentum for the optimization.
  optimizer = tf.train.MomentumOptimizer(learning_rate,
                                         0.9).minimize(loss,
                                                       global_step=batch)

  # Predictions for the current training minibatch.
  # train_prediction = tf.nn.softmax(logits)
  train_prediction = pred
  variable_summaries(train_prediction,"prediction")

  # Predictions for the test and validation, which we'll compute less often.
  # eval_prediction = tf.nn.softmax(model(eval_data))
  # eval_prediction = model(eval_data)

  # Small utility function to evaluate a dataset by feeding batches of data to
  # {eval_data} and pulling the results from {eval_predictions}.
  # Saves memory and enables this to run on smaller GPUs.
  def eval_in_batches(data, sess):
    """Get all predictions for a dataset by running it in small batches."""
    size = data.shape[0]
    if size < EVAL_BATCH_SIZE:
      raise ValueError("batch size for evals larger than dataset: %d" % size)
    predictions = numpy.ndarray(shape=(size, NUM_LABELS), dtype=numpy.float32)
    for begin in range(0, size, EVAL_BATCH_SIZE):
      end = begin + EVAL_BATCH_SIZE
      if end <= size:
        predictions[begin:end, :] = sess.run(
            eval_prediction,
            feed_dict={eval_data: data[begin:end, ...]})
      else:
        batch_predictions = sess.run(
            eval_prediction,
            feed_dict={eval_data: data[-EVAL_BATCH_SIZE:, ...]})
        predictions[begin:, :] = batch_predictions[begin - size:, :]
    return predictions

  # check_op = tf.add_check_numerics_ops() # To check for NAN
  check_op = None

  # Create a saver.
  saver = tf.train.Saver() # Default to save all savable objets
  # Remember the op we want to run by adding it to a collection.
  #tf.add_to_collection('mon_decoder', model(decode_node))


  # Create a local session to run the training.
  start_time = time.time()
  with tf.Session() as sess:

    # Merge all the summaries
    merged = tf.summary.merge_all()
    train_writer = tf.summary.FileWriter('/home/gerey/hms_lung/log2/',
                                          sess.graph)

    # Run all the initializers to prepare the trainable parameters.
    tf.global_variables_initializer().run()
    print('Initialized!')
    # Loop through training steps.
    train_size = 10000  # TODO
    it = itertools.cycle(batcher(((f,t) for _,_,f,t in train_data.features_and_targets()),
                               BATCH_SIZE))
    for step in range(int(num_epochs * train_size) // BATCH_SIZE):

      batch_data, batch_labels = next(it)
      # TODO: what if datatype()==tf.float16 ?
      batch_data = batch_data.astype(numpy.float32) / PIXEL_DEPTH - 0.5

      if check_op is not None:
          assert not numpy.isnan(batch_data.sum())
          assert not numpy.isnan(batch_labels.sum())

      # This dictionary maps the batch data (as a numpy array) to the
      # node in the graph it should be fed to.
      feed_dict = {train_data_node: batch_data,
                   train_labels_node: batch_labels}

      # Run the optimizer to update weights.
      if check_op is not None:
          sess.run([optimizer, check_op], feed_dict=feed_dict)
      else:
          _, summary = sess.run([optimizer, merged], feed_dict=feed_dict)
          train_writer.add_summary(summary, step)

      # Saves checkpoint, which by default also exports a meta_graph
      if step % 100 == 0:
          saver.save(sess, '/home/gerey/hms_lung/models_coefs/2-proper-samples/', global_step=step)
          print("Saved step %d" % (step,))

      # print some extra information once reach the evaluation frequency
      if step % EVAL_FREQUENCY == 0:
        # fetch some extra nodes' data
        if check_op is not None:
            l, lr, predictions, _ = sess.run([loss, learning_rate, train_prediction, check_op],
                                          feed_dict=feed_dict)
        else:
            l, lr, predictions = sess.run([loss, learning_rate, train_prediction],
                                           feed_dict=feed_dict)

        elapsed_time = time.time() - start_time
        start_time = time.time()
        print('Step %d (epoch %.2f), %.1f ms' %
              (step, float(step) * BATCH_SIZE / train_size,
               1000 * elapsed_time / EVAL_FREQUENCY))
        print('Minibatch loss: %.3f, learning rate: %.6f' % (l, lr))
        print('Minibatch error: %.1f%%' % error_rate(predictions, batch_labels))
        # print('Validation error: %.1f%%' % error_rate(
        #     eval_in_batches(validation_data, sess), validation_labels))
        sys.stdout.flush()
    # Finally print the result!
    # test_error = error_rate(eval_in_batches(test_data, sess), test_labels)
    # print('Test error: %.1f%%' % test_error)


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  # Unplugged
  #parser.add_argument(
  #    '--use_fp16',
  #    default=False,
  #    help='Use half floats instead of full floats if True.',
  #    action='store_true')
  #parser.add_argument(
  #    '--self_test',
  #    default=False,
  #    action='store_true',
  #    help='True if running a self test.')

  FLAGS, unparsed = parser.parse_known_args()
  tf.app.run(main=main, argv=[sys.argv[0]] + unparsed)
