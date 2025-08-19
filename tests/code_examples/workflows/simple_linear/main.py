"""Main entry point for simple linear workflow example."""


def main() -> None:
    """Main entry point function."""
    from .processor import process_data
    
    data = {"value": 42}
    result = process_data(data)
    print(f"Result: {result}")


if __name__ == "__main__":
    main()