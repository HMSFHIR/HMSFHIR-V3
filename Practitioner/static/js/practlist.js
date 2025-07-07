// Search functionality
document.getElementById('searchInput').addEventListener('keyup', function() {
    const searchValue = this.value.toLowerCase();
    const tableRows = document.querySelectorAll('.practitioners-table tbody tr');
    
    tableRows.forEach(row => {
        const name = row.querySelector('.practitioner-name').textContent.toLowerCase();
        const id = row.querySelector('.practitioner-id').textContent.toLowerCase();
        const role = row.querySelector('.role-badge').textContent.toLowerCase();
        const email = row.querySelectorAll('.contact-info')[1].textContent.toLowerCase();
        
        if (name.includes(searchValue) || id.includes(searchValue) || 
            role.includes(searchValue) || email.includes(searchValue)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
});
