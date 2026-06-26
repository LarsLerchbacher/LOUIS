import asyncio

async def worker(name, queue):
    while True:
        # Get a "work item" out of the queue.
        task = await queue.get()
        
        # Sleep for the "task" to simulate work.
        print(f"Worker {name} started task {task}")
        await asyncio.sleep(task)
        print(f"Worker {name} finished task {task}")
        
        # Notify the queue that the "work item" has been processed.
        queue.task_done()

async def main():
    # Create a queue that will hold "work items".
    queue = asyncio.Queue()
    
    # Create three worker tasks to process the queue concurrently.
    tasks = []
    for i in range(3):
        task = asyncio.create_task(worker(f"Worker-{i}", queue))
        tasks.append(task)
    
    # Add "work items" to the queue.
    total_tasks = 10
    for task in range(total_tasks):
        await queue.put(task)
    
    # Wait until the queue is fully processed.
    await queue.join()
    
    # Cancel our worker tasks.
    for task in tasks:
        task.cancel()
    
    # Wait until all worker tasks are cancelled.
    await asyncio.gather(*tasks, return_exceptions=True)
    
    print("All tasks completed!")

# Run the main function.
asyncio.run(main())
