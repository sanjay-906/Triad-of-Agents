from fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("Dish Ingredients Service")


DISHES = {
    "chicken biryani": ["Basmati rice", "Chicken", "Onion", "Tomato", "Yogurt", "Ginger", "Garlic", "Green chili", "Biryani masala", "Turmeric", "Cumin", "Coriander", "Mint leaves", "Cilantro", "Cooking oil", "Salt"],
    "margherita pizza": ["Pizza dough", "Tomato sauce", "Mozzarella cheese", "Fresh basil", "Olive oil", "Salt"],
    "spaghetti carbonara": ["Spaghetti", "Eggs", "Pancetta", "Parmesan cheese", "Black pepper", "Salt"],
    "butter chicken": ["Chicken", "Butter", "Tomato puree", "Heavy cream", "Yogurt", "Ginger", "Garlic", "Garam masala", "Turmeric", "Cumin", "Coriander", "Chili powder", "Salt"],
    "caesar salad": ["Romaine lettuce", "Croutons", "Parmesan cheese", "Caesar dressing", "Lemon juice", "Garlic", "Black pepper", "Salt"],
    "tacos": ["Taco shells", "Ground beef", "Lettuce", "Tomato", "Cheddar cheese", "Onion", "Sour cream", "Salsa", "Cumin", "Chili powder", "Salt"],
    "pancakes": ["All-purpose flour", "Milk", "Eggs", "Butter", "Sugar", "Baking powder", "Vanilla extract", "Salt"],
    "greek salad": ["Cucumber", "Tomato", "Red onion", "Green bell pepper", "Kalamata olives", "Feta cheese", "Olive oil", "Lemon juice", "Oregano", "Salt", "Black pepper"],
    "beef burger": ["Ground beef", "Burger buns", "Cheddar cheese", "Lettuce", "Tomato", "Onion", "Pickles", "Ketchup", "Mustard", "Mayonnaise", "Salt", "Black pepper"],
}


@mcp.tool()
def get_ingredients(name: str) -> str:
    """Return all ingredients for a dish."""

    dish_name = name.strip().lower()

    ingredients = DISHES.get(dish_name)

    if ingredients is None:
        return f"No dish found with name '{name}'."

    return (
        f"Ingredients for {name}:\n" + "\n".join(f"- {ingredient}" for ingredient in ingredients)
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=1905)
