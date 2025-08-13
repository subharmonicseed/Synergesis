from neo4j import GraphDatabase
import os

def test_neo4j_connection():
    uri = "bolt://localhost:7687"
    user = "neo4j"
    password = "blackstar1989"
    database = "Synergesis"
    
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
    test_neo4j_connection()
