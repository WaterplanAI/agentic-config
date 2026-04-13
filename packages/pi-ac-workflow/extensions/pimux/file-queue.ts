import * as path from "node:path";

const fileOperationQueues = new Map<string, Promise<void>>();

export async function withQueuedFileOperation<T>(filePath: string, operation: () => Promise<T>): Promise<T> {
	const key = path.resolve(filePath);
	const previous = fileOperationQueues.get(key) ?? Promise.resolve();
	let release!: () => void;
	const gate = new Promise<void>((resolve) => {
		release = resolve;
	});
	const queued = previous.catch(() => undefined).then(() => gate);
	fileOperationQueues.set(key, queued);
	await previous.catch(() => undefined);
	try {
		return await operation();
	} finally {
		release();
		if (fileOperationQueues.get(key) === queued) {
			fileOperationQueues.delete(key);
		}
	}
}
