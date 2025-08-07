/**
 * Simple TypeScript class for testing basic functionality.
 * 
 * This file contains basic TypeScript constructs to test
 * GraphBuilder's ability to parse and analyze TypeScript code.
 */

export interface ValueHolder {
  getValue(): string;
  setValue(value: string): void;
}

export class SimpleClass implements ValueHolder {
  private value: string;
  
  constructor(value: string) {
    this.value = value;
  }
  
  public getValue(): string {
    return this.value;
  }
  
  public setValue(value: string): void {
    this.value = value;
  }
  
  public processValue(): string {
    const processed = this.internalProcess();
    return processed;
  }
  
  private internalProcess(): string {
    return `Processed: ${this.value}`;
  }
}

export function simpleFunction(): string {
  return "Hello from TypeScript";
}

export function functionWithParameter(name: string): string {
  return `Hello, ${name}!`;
}

export function genericFunction<T>(item: T): T {
  return item;
}

// Type alias
export type ProcessorResult = {
  success: boolean;
  data: string;
  timestamp: Date;
};

// Enum
export enum Status {
  PENDING = "pending",
  PROCESSING = "processing", 
  COMPLETED = "completed",
  FAILED = "failed"
}

// Module-level constants
export const MODULE_CONSTANT = "test_constant";
export const DEFAULT_STATUS = Status.PENDING;

// Module-level usage
const instance = new SimpleClass("test");
const result = simpleFunction();