import { drizzle } from 'drizzle-orm/postgres-js';
import postgres from 'postgres';
import * as schema from '../shared/schema';

// Create the postgres connection
const connectionString = process.env.DATABASE_URL || "postgresql://localhost:5432/mastra";

// Create postgres client
export const sql = postgres(connectionString, {
  max: 10,
  idle_timeout: 20,
  connect_timeout: 10,
});

// Create drizzle instance with schema
export const db = drizzle(sql, { schema });

// Export schema for use in other parts of the application
export { schema };