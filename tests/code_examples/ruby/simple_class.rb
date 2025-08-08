# Simple Ruby class for testing basic functionality.
#
# This file contains basic Ruby constructs to test
# GraphBuilder's ability to parse and analyze Ruby code.

class SimpleClass
  attr_reader :value
  attr_writer :name
  attr_accessor :status
  
  def initialize(value)
    @value = value
    @name = nil
    @status = 'initialized'
  end
  
  def get_value
    @value
  end
  
  def set_value(new_value)
    @value = new_value
  end
  
  def process_value
    processed = internal_process
    processed
  end
  
  private
  
  def internal_process
    "Processed: #{@value}"
  end
end

def simple_function
  'Hello from Ruby'
end

def function_with_parameter(name)
  "Hello, #{name}!"
end

def function_with_block
  yield if block_given?
end

def function_with_multiple_params(name, age = 25, *args, **kwargs)
  result = "Name: #{name}, Age: #{age}"
  result += ", Args: #{args}" unless args.empty?
  result += ", Kwargs: #{kwargs}" unless kwargs.empty?
  result
end

# Module-level constants
MODULE_CONSTANT = 'test_constant'
DEFAULT_VALUE = 42

# Module-level variables
$global_variable = 'global'
@@class_variable = 'class_variable'

# Usage examples
instance = SimpleClass.new('test_value')
result = simple_function
processed = instance.process_value

# Method with different parameter types
def demonstrate_ruby_features(required, optional = 'default', *splat, keyword:, optional_keyword: nil, **double_splat, &block)
  {
    required: required,
    optional: optional,
    splat: splat,
    keyword: keyword,
    optional_keyword: optional_keyword,
    double_splat: double_splat,
    has_block: block_given?
  }
end