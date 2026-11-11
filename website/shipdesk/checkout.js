const sessionId = new URLSearchParams(location.search).get('session_id');
const status = document.querySelector('#status');

if (sessionId) {
  document.querySelector('#plan').hidden = true;
  document.querySelector('#delivery').hidden = false;
  claim();
}

async function claim() {
  try {
    const response = await fetch('/api/shipdesk?action=claim', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
    status.textContent = 'Payment verified. Download ShipDesk and save your license.';
    document.querySelector('#license').value = result.license;
    document.querySelector('#entitlement').hidden = false;
    document.querySelector('#download').onclick = () => download(result.license);
  } catch (error) {
    status.textContent = error.message;
  }
}

async function download(license) {
  try {
    const response = await fetch('/api/shipdesk?action=download', {
      headers: { Authorization: 'Bearer ' + license },
    });
    if (!response.ok) throw new Error((await response.json()).error);
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url;
    link.download = 'ShipDesk.zip';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    status.textContent = error.message;
  }
}
