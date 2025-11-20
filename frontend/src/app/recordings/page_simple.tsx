'use client';

export default function RecordingsPageSimple() {
  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-6">
          📹 Meeting Recordings (Simple Test)
        </h1>
        
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-600 mb-4">
            If you can see this, the page is loading correctly.
          </p>
          
          <button
            onClick={() => {
              console.log('Button clicked!');
              
              // Test API call
              const token = localStorage.getItem('jwt_token');
              console.log('Token:', token ? '✅ Found' : '❌ Not found');
              
              if (!token) {
                alert('No JWT token found. Please login first.');
                return;
              }
              
              fetch('http://localhost:8000/api/v1/database/recordings?limit=5', {
                headers: {
                  'Authorization': `Bearer ${token}`
                }
              })
              .then(r => {
                console.log('Response status:', r.status);
                return r.json();
              })
              .then(data => {
                console.log('Data:', data);
                alert('Success! Check console for data.');
              })
              .catch(err => {
                console.error('Error:', err);
                alert('Error: ' + err.message);
              });
            }}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Test API Call
          </button>
          
          <div className="mt-4 p-4 bg-gray-50 rounded">
            <p className="text-sm text-gray-600">
              Click the button above to test the API call manually.
              Check the browser Console for results.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

