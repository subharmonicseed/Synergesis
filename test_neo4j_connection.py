from neo4j import GraphDatabase
import os

def test_connection():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "neo4j")
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session(database=database) as session:
            result = session.run("RETURN 1 as number")
            print("Successfully connected to Neo4j!")
            print("Test query result:", result.single()["number"])
    except Exception as e:
        print(f"Connection failed: {e}")
    finally:
        if 'driver' in locals():
            driver.close()

if __name__ == "__main__":
    test_connection()
