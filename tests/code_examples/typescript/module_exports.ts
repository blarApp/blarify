/**
 * TypeScript module exports example for testing import/export relationship parsing.
 */

// Import from other test modules
import { SimpleClass, simpleFunction, Status } from './simple_class';
import { 
  ProcessableEntity, 
  TextProcessor, 
  AdvancedProcessor,
  createProcessor 
} from './interface_inheritance';

// Re-export some items
export { SimpleClass, Status } from './simple_class';
export { ProcessableEntity, createProcessor } from './interface_inheritance';

// Default export
export default class ModuleExportExample {
  private processors: Map<string, ProcessableEntity> = new Map();
  private simpleObjects: SimpleClass[] = [];
  
  constructor() {
    this.initialize();
  }
  
  private initialize(): void {
    // Use imported functions and classes
    const basicProcessor = createProcessor("basic", "module-1", "Module Basic");
    const advancedProcessor = createProcessor("advanced", "module-2", "Module Advanced");
    
    this.processors.set("basic", basicProcessor);
    this.processors.set("advanced", advancedProcessor);
    
    // Create simple objects
    this.simpleObjects.push(new SimpleClass("module_test_1"));
    this.simpleObjects.push(new SimpleClass("module_test_2"));
  }
  
  public async processWithType(
    data: string, 
    processorType: "basic" | "advanced"
  ): Promise<string> {
    const processor = this.processors.get(processorType);
    if (!processor) {
      throw new Error(`Processor type ${processorType} not found`);
    }
    
    return await processor.process(data);
  }
  
  public getSimpleValues(): string[] {
    return this.simpleObjects.map(obj => obj.getValue());
  }
  
  public demonstrateImports(): Record<string, any> {
    // Use imported function
    const greeting = simpleFunction();
    
    // Use imported enum
    const currentStatus = Status.PROCESSING;
    
    // Get processor info
    const processorNames = Array.from(this.processors.keys());
    
    return {
      greeting,
      currentStatus,
      processorNames,
      simpleValues: this.getSimpleValues()
    };
  }
}

// Named exports
export class UtilityHelper {
  static formatResult(result: string): string {
    return `[FORMATTED] ${result}`;
  }
  
  static async processMultiple(
    items: string[], 
    processor: ProcessableEntity
  ): Promise<string[]> {
    const results: string[] = [];
    
    for (const item of items) {
      const processed = await processor.process(item);
      results.push(this.formatResult(processed));
    }
    
    return results;
  }
}

// Function that uses multiple imports
export async function demonstrateModuleUsage(): Promise<void> {
  const example = new ModuleExportExample();
  
  // Use the default export
  const result = await example.processWithType("test data", "basic");
  const formatted = UtilityHelper.formatResult(result);
  
  // Use imported classes directly
  const textProcessor = new TextProcessor("direct-1", "Direct Processor");
  const directResult = await textProcessor.process("direct test");
  
  console.log("Module result:", formatted);
  console.log("Direct result:", directResult);
  console.log("Demo data:", example.demonstrateImports());
}

// Module-level constants using imports
export const MODULE_PROCESSORS = {
  basic: createProcessor("basic", "module-basic", "Module Basic Processor"),
  advanced: createProcessor("advanced", "module-advanced", "Module Advanced Processor")
};

export const SIMPLE_INSTANCE = new SimpleClass("module_constant");