from neo4j import GraphDatabase
import time

def test_connection():
    uri = "bolt://localhost:7687"
    user = "neo4j"
    password = "neo4j"
    
    try:
        # Wait a bit for Neo4j to start
        time.sleep(10)
        
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            result = session.run("RETURN 1")
            print("Successfully connected to Neo4j!")
            print("Result:", result.single()[0])
        
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")
    finally:
        if driver:
            driver.close()

if __name__ == "__main__":
    test_connection()
