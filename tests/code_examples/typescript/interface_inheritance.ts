/**
 * TypeScript interface inheritance example for testing relationship parsing.
 */

// Base interfaces
export interface Identifiable {
  id: string;
  getName(): string;
}

export interface Processable {
  process(data: string): Promise<string>;
}

// Extended interface
export interface ProcessableEntity extends Identifiable, Processable {
  status: string;
  getStatus(): string;
  setStatus(status: string): void;
}

// Abstract base class
export abstract class BaseEntity implements Identifiable {
  protected _id: string;
  protected _name: string;
  
  constructor(id: string, name: string) {
    this._id = id;
    this._name = name;
  }
  
  get id(): string {
    return this._id;
  }
  
  public getName(): string {
    return this._name;
  }
  
  public abstract getType(): string;
}

// Concrete implementation
export class TextProcessor extends BaseEntity implements ProcessableEntity {
  private _status: string = "ready";
  private _prefix: string;
  
  constructor(id: string, name: string, prefix: string = "") {
    super(id, name);
    this._prefix = prefix;
  }
  
  public getType(): string {
    return "TextProcessor";
  }
  
  get status(): string {
    return this._status;
  }
  
  public getStatus(): string {
    return this._status;
  }
  
  public setStatus(status: string): void {
    this._status = status;
  }
  
  public async process(data: string): Promise<string> {
    this.setStatus("processing");
    
    // Simulate async processing
    await new Promise(resolve => setTimeout(resolve, 10));
    
    const result = `${this._prefix}${data}`;
    this.setStatus("completed");
    
    return result;
  }
  
  public batchProcess(items: string[]): Promise<string[]> {
    return Promise.all(items.map(item => this.process(item)));
  }
}

// Advanced processor with additional interfaces
export interface Configurable {
  configure(options: Record<string, any>): void;
}

export class AdvancedProcessor extends TextProcessor implements Configurable {
  private _suffix: string = "";
  private _options: Record<string, any> = {};
  
  constructor(id: string, name: string, prefix?: string) {
    super(id, name, prefix);
  }
  
  public configure(options: Record<string, any>): void {
    this._options = { ...this._options, ...options };
    if (options.suffix) {
      this._suffix = options.suffix;
    }
  }
  
  public async process(data: string): Promise<string> {
    const baseResult = await super.process(data);
    return `${baseResult}${this._suffix}`;
  }
  
  public getType(): string {
    return "AdvancedProcessor";
  }
}

// Factory function
export function createProcessor(
  type: "basic" | "advanced", 
  id: string, 
  name: string
): ProcessableEntity {
  switch (type) {
    case "basic":
      return new TextProcessor(id, name);
    case "advanced":
      return new AdvancedProcessor(id, name);
    default:
      throw new Error(`Unknown processor type: ${type}`);
  }
}

// Usage example
export async function exampleUsage(): Promise<void> {
  const processor = createProcessor("basic", "test-1", "Example Processor");
  const result = await processor.process("Hello World");
  console.log(result);
}