
function clearForm() {
    document.getElementById('patient_id').value = '';
    document.getElementById('national_id').value = '';
}

function toggleRawData() {
    const rawData = document.getElementById('rawData');
    if (rawData.style.display === 'none') {
        rawData.style.display = 'block';
    } else {
        rawData.style.display = 'none';
    }
}

function savePatient() {
    // Add functionality to save patient to your local database
    alert('Save patient functionality - implement based on your needs');
}

function printData() {
    window.print();
}
