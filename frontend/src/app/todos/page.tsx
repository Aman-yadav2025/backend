import { createClient } from "@/utils/supabase/server";
import { cookies } from "next/headers";

export default async function Page() {
  const cookieStore = await cookies();
  const supabase = createClient(cookieStore);

  const { data: todos } = await supabase.from("todos").select();

  return (
    <div className="p-8 max-w-md mx-auto">
      <h1 className="text-2xl font-bold mb-4 text-slate-800">Supabase Todos</h1>
      {todos && todos.length > 0 ? (
        <ul className="space-y-2">
          {todos.map((todo) => (
            <li key={todo.id} className="p-3 bg-white shadow rounded border text-slate-700">
              {todo.name}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-slate-500">No todos found or table does not exist yet.</p>
      )}
    </div>
  );
}
