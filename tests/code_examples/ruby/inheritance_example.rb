# Ruby class inheritance and requires example for testing relationship parsing.

require_relative 'simple_class'
require_relative 'module_example'

# Require standard libraries (these should show up as external dependencies)
require 'json'
require 'net/http'
require 'uri'

class InheritanceExample < SimpleClass
  include Processable
  include Configurable
  
  attr_reader :children, :metadata
  
  def initialize(value, metadata = {})
    super(value)
    @children = []
    @metadata = metadata
    @processor = nil
  end
  
  def add_child(child)
    @children << child
    child.parent = self if child.respond_to?(:parent=)
  end
  
  def process_value
    # Call parent method
    base_result = super
    
    # Add inheritance-specific processing
    enhanced_result = enhance_processing(base_result)
    
    # Process children if any
    if @children.any?
      child_results = @children.map(&:process_value)
      enhanced_result += " [Children: #{child_results.join(', ')}]"
    end
    
    enhanced_result
  end
  
  def process(data)
    # Implementation from Processable module
    result = super(data)
    "#{get_value}: #{result}"
  end
  
  def create_processor(type = :text)
    @processor = case type
                when :text
                  TextProcessor.new("#{get_value}_processor")
                when :advanced
                  AdvancedProcessor.new("#{get_value}_advanced")
                else
                  BaseProcessor.new("#{get_value}_base")
                end
  end
  
  def process_with_processor(data)
    create_processor(:advanced) unless @processor
    @processor.process(data)
  end
  
  def to_json_representation
    # Use required JSON library
    JSON.generate({
      value: get_value,
      status: status,
      metadata: @metadata,
      children_count: @children.length,
      processor_type: @processor&.get_type
    })
  end
  
  def fetch_external_data(url)
    # Use required networking libraries
    uri = URI.parse(url)
    response = Net::HTTP.get_response(uri)
    
    if response.code == '200'
      JSON.parse(response.body)
    else
      { error: "Failed to fetch data: #{response.code}" }
    end
  rescue StandardError => e
    { error: "Exception: #{e.message}" }
  end
  
  private
  
  def enhance_processing(base_result)
    "[ENHANCED] #{base_result}"
  end
end

# Multiple inheritance through modules
class MultipleInheritanceExample < InheritanceExample
  include Timestampable
  
  def initialize(value, metadata = {}, timestamp_enabled = true)
    super(value, metadata)
    @timestamp_enabled = timestamp_enabled
  end
  
  def process_value
    result = super
    
    if @timestamp_enabled
      add_timestamp_to_result(result)
    else
      result
    end
  end
  
  def process(data)
    result = super(data)
    @timestamp_enabled ? add_timestamp : result
  end
  
  private
  
  def add_timestamp_to_result(result)
    "[#{Time.now.strftime('%Y-%m-%d %H:%M:%S')}] #{result}"
  end
end

# Class with complex inheritance chain
class ComplexExample < MultipleInheritanceExample
  def initialize(value, metadata = {})
    super(value, metadata, true)
    @processing_chain = []
  end
  
  def process_value
    add_to_chain('process_value_start')
    
    # Call all the way up the inheritance chain
    result = super
    
    add_to_chain('process_value_end')
    
    "#{result} [Chain: #{@processing_chain.join(' -> ')}]"
  end
  
  def get_inheritance_chain
    ancestors = self.class.ancestors.select { |a| a.is_a?(Class) }
    ancestors.map(&:name)
  end
  
  def get_included_modules
    self.class.included_modules.map(&:name)
  end
  
  private
  
  def add_to_chain(step)
    @processing_chain << step
  end
end

# Factory functions that use inheritance
def create_example(type, value, **options)
  case type
  when :simple
    InheritanceExample.new(value, options[:metadata] || {})
  when :multiple
    MultipleInheritanceExample.new(value, options[:metadata] || {}, options[:timestamp] || true)
  when :complex
    ComplexExample.new(value, options[:metadata] || {})
  else
    raise ArgumentError, "Unknown example type: #{type}"
  end
end

def demonstrate_inheritance
  # Create examples with different inheritance levels
  simple_example = create_example(:simple, 'simple_test')
  multiple_example = create_example(:multiple, 'multiple_test', timestamp: true)
  complex_example = create_example(:complex, 'complex_test')
  
  # Add child relationships
  simple_example.add_child(SimpleClass.new('child_1'))
  multiple_example.add_child(create_example(:simple, 'child_2'))
  
  # Process values to demonstrate inheritance
  results = {
    simple: simple_example.process_value,
    multiple: multiple_example.process_value,
    complex: complex_example.process_value,
    complex_chain: complex_example.get_inheritance_chain,
    complex_modules: complex_example.get_included_modules
  }
  
  # Demonstrate JSON serialization
  results[:json_representation] = JSON.parse(simple_example.to_json_representation)
  
  results
end

# Module-level constants using inheritance
SIMPLE_EXAMPLE = create_example(:simple, 'module_simple')
COMPLEX_EXAMPLE = create_example(:complex, 'module_complex')

# Demonstrate usage at module level
example_result = demonstrate_inheritance