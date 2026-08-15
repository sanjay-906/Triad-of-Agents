from fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("Dish Preparation Service")


@mcp.tool()
async def prepare_dish(name: str, ingredients: list[str]) -> str:
    """Prepare a dish."""
    if ingredients is None or not isinstance(ingredients, list):
        return str({
            "response": f"ingredients should be a list of strings, got {type(ingredients).__name__}",
            "time": "N/A",
            "table_number": None,
            "status": "error",
        })

    return str({
        "response": f"{name} prepared successfully",
        "time": "30 minutes",
        "table_number": 5,
        "status": "ready on the table",
    })


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=1906)
