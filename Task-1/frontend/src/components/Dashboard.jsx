import { useAuth } from '../context/AuthContext';

export default function Dashboard() {
  const { user, logout } = useAuth();

  return (
    <div className="max-w-4xl mx-auto mt-8 p-6">
      <div className="bg-white rounded shadow p-6">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl font-bold">Dashboard</h2>
          <button
            onClick={logout}
            className="bg-red-500 text-white px-4 py-2 rounded hover:bg-red-600"
          >
            Logout
          </button>
        </div>
        
        <div className="bg-blue-50 p-4 rounded mb-6">
          <h3 className="font-bold mb-2">User Information</h3>
          <p><strong>Username:</strong> {user?.username}</p>
          <p><strong>Email:</strong> {user?.email}</p>
          <p><strong>Role:</strong> <span className="uppercase font-semibold">{user?.role}</span></p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="border p-4 rounded">
            <h4 className="font-bold mb-2">Containers</h4>
            <p className="text-gray-600">Manage your containers</p>
          </div>
          <div className="border p-4 rounded">
            <h4 className="font-bold mb-2">Networks</h4>
            <p className="text-gray-600">Configure networks</p>
          </div>
          <div className="border p-4 rounded">
            <h4 className="font-bold mb-2">Hosts</h4>
            <p className="text-gray-600">Manage remote hosts</p>
          </div>
        </div>
      </div>
    </div>
  );
}
