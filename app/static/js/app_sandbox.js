const { createApp, ref, onMounted } = Vue;

const BooksApp = {
    compilerOptions: { delimiters: ['[[', ']]'] },
    setup() {
        const searchQuery = ref('');
        const searchResults = ref([]);
        const searchLoading = ref(false);
        const searchError = ref('');

        const topicGroups = ref([]);
        const performanceLoading = ref(false);
        const performanceError = ref('');

        const fetchInitialPerformanceBooks = async () => {
            performanceLoading.value = true;
            performanceError.value = '';
            try {
                const res = await axios.get('/api/books/performance');
                if (res.data && res.data.success) {
                    topicGroups.value = res.data.topics || [];
                }
            } catch (err) {
                console.error('Failed to load performance-based books', err);
            } finally {
                performanceLoading.value = false;
            }
        };

        const searchBooks = async () => {
            if (!searchQuery.value.trim()) return;
            searchLoading.value = true;
            searchError.value = '';

            try {
                const res = await axios.get('/api/books/search', {
                    params: { q: searchQuery.value }
                });
                if (res.data && res.data.success) {
                    searchResults.value = res.data.books || [];
                } else {
                    searchError.value = (res.data && res.data.message) || 'Search failed.';
                }
            } catch (err) {
                console.error('Book search failed', err);
                searchError.value = 'Network error while searching for books.';
            } finally {
                searchLoading.value = false;
            }
        };

        const loadPerformanceBooks = async () => {
            performanceLoading.value = true;
            performanceError.value = '';

            try {
                const res = await axios.get('/api/books/performance');
                if (res.data && res.data.success) {
                    topicGroups.value = res.data.topics || [];
                } else {
                    performanceError.value = (res.data && res.data.message) || 'Failed to load performance-based recommendations.';
                }
            } catch (err) {
                console.error('Failed to refresh performance-based books', err);
                performanceError.value = 'Network error while loading recommendations.';
            } finally {
                performanceLoading.value = false;
            }
        };

        const markViewed = async (book) => {
            try {
                await axios.post('/api/books/mark-viewed', {
                    id: book.id,
                    book_key: book.book_key
                });
                book.is_viewed = true;
            } catch (err) {
                console.error('Failed to mark book as viewed', err);
            }
        };

        onMounted(() => {
            fetchInitialPerformanceBooks();
        });

        return {
            searchQuery,
            searchResults,
            searchLoading,
            searchError,
            topicGroups,
            performanceLoading,
            performanceError,
            searchBooks,
            loadPerformanceBooks,
            markViewed
        };
    }
};

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('books-app')) {
        createApp(BooksApp).mount('#books-app');
    }
});
