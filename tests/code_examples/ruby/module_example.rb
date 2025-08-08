# Ruby module and class inheritance example for testing relationship parsing.

module Processable
  def process(data)
    "Processing: #{data}"
  end
  
  def batch_process(items)
    items.map { |item| process(item) }
  end
  
  def self.included(base)
    base.extend(ClassMethods)
  end
  
  module ClassMethods
    def create_processor(name)
      new(name)
    end
  end
end

module Configurable
  attr_accessor :config
  
  def configure(options = {})
    @config ||= {}
    @config.merge!(options)
  end
  
  def get_config(key)
    @config&.fetch(key, nil)
  end
end

class BaseProcessor
  include Processable
  include Configurable
  
  attr_reader :name, :created_at
  
  def initialize(name)
    @name = name
    @created_at = Time.now
    configure(default_options)
  end
  
  def get_name
    @name
  end
  
  def get_type
    self.class.name
  end
  
  protected
  
  def default_options
    { enabled: true, verbose: false }
  end
end

class TextProcessor < BaseProcessor
  attr_accessor :prefix, :suffix
  
  def initialize(name, prefix = '')
    super(name)
    @prefix = prefix
    @suffix = ''
  end
  
  def process(data)
    result = "#{@prefix}#{data}#{@suffix}"
    log_processing(result) if get_config(:verbose)
    result
  end
  
  def set_suffix(suffix)
    @suffix = suffix
  end
  
  private
  
  def log_processing(result)
    puts "Processed: #{result}"
  end
end

class AdvancedProcessor < TextProcessor
  def initialize(name, prefix = '', suffix = '')
    super(name, prefix)
    @suffix = suffix
  end
  
  def process(data)
    # Call parent method
    base_result = super(data)
    
    # Add advanced processing
    advanced_result = apply_advanced_processing(base_result)
    advanced_result
  end
  
  def batch_process(items)
    # Override to add advanced batch processing
    results = super(items)
    results.map { |result| "[ADVANCED] #{result}" }
  end
  
  private
  
  def apply_advanced_processing(data)
    "[ENHANCED] #{data}"
  end
end

# Mixin module
module Timestampable
  def self.included(base)
    base.extend(ClassMethods)
  end
  
  def add_timestamp
    "#{Time.now.strftime('%Y-%m-%d %H:%M:%S')}: #{self}"
  end
  
  module ClassMethods
    def with_timestamp(value)
      "#{Time.now.strftime('%Y-%m-%d %H:%M:%S')}: #{value}"
    end
  end
end

# Class that includes multiple modules
class TimestampedProcessor < AdvancedProcessor
  include Timestampable
  
  def process(data)
    result = super(data)
    add_timestamp_to_result(result)
  end
  
  private
  
  def add_timestamp_to_result(result)
    "[#{Time.now.strftime('%H:%M:%S')}] #{result}"
  end
end

# Factory method
def create_processor(type, name, **options)
  case type
  when :basic
    BaseProcessor.new(name)
  when :text
    processor = TextProcessor.new(name, options[:prefix] || '')
    processor.set_suffix(options[:suffix] || '')
    processor
  when :advanced
    AdvancedProcessor.new(name, options[:prefix] || '', options[:suffix] || '')
  when :timestamped
    TimestampedProcessor.new(name, options[:prefix] || '', options[:suffix] || '')
  else
    raise ArgumentError, "Unknown processor type: #{type}"
  end
end

# Module-level usage
DEFAULT_PROCESSOR = create_processor(:text, 'default', prefix: '>> ')
ADVANCED_INSTANCE = create_processor(:advanced, 'advanced_example')

# Demonstrate module usage
def demonstrate_modules
  processor = create_processor(:timestamped, 'demo_processor', prefix: 'DEMO: ')
  
  # Configure the processor
  processor.configure(verbose: true, custom_option: 'test')
  
  # Process some data
  result = processor.process('Hello World')
  
  # Batch process
  batch_results = processor.batch_process(['item1', 'item2', 'item3'])
  
  {
    single_result: result,
    batch_results: batch_results,
    processor_type: processor.get_type,
    processor_config: processor.config
  }
end